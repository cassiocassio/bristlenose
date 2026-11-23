import Foundation

/// The "Read shared screens" preference (Settings ▸ Transcription) — whether the
/// serve reads the text on screens participants shared in their recordings, for
/// the Screens lens (`docs/design-screens.md`). Its own key, **on by default**,
/// and nothing to do with Diagnostics: the lens left that menu's company when
/// it shipped in the main app.
///
/// It reaches the sidecar as `BRISTLENOSE_SCREEN_TEXT` (`overlayPreferences`),
/// always stated: "1" on, "0" off. The explicit "0" matters — the server deletes
/// what it read when it sees it, while an unset variable means the CLI default
/// and deletes nothing.
enum ScreenTextPreference {
    static let key = "readSharedScreens"

    static let defaultValue = true

    /// The stored preference, or the default when it has never been touched.
    static func isEnabled(_ defaults: UserDefaults = .standard) -> Bool {
        defaults.object(forKey: key) as? Bool ?? defaultValue
    }
}

/// How far the serve's screen-reading job has got through a project's
/// recordings — the Screens lens's background work (`docs/design-screens.md`),
/// shown as one more activity on the sidebar status line, like a copy or a
/// cloud batch.
///
/// Read from `GET /api/projects/1/screens/status`. Deliberately its own type
/// and its own store, not `RunProgressEvent` / `PipelineProgress`: screen
/// reading is not a pipeline stage, has no estimator behind it, and cannot be
/// stopped, so it borrows none of the run's ladder, ring or ETA model.
struct ScreenReadingProgress: Equatable {
    /// Recordings read so far, and in all.
    let done: Int
    let total: Int
    /// Seconds of recording read so far, and in all — the denominator the
    /// server's `rate` is measured against.
    let secondsDone: Double
    let secondsTotal: Double
    /// Seconds of recording read per second of wall clock, measured by the
    /// server; nil until it has measured one. **The only source of an ETA** —
    /// there is no constant to fall back on, so a warm-up says nothing about
    /// time rather than guessing.
    let rate: Double?

    /// Remaining wall-clock seconds, or nil while there is no measured rate.
    var etaSeconds: Double? {
        guard let rate, rate.isFinite, rate > 0 else { return nil }
        let left = secondsTotal - secondsDone
        guard left.isFinite, left > 0 else { return nil }
        return left / rate
    }

    /// Parse the status body, or nil when there is nothing to show: the job is
    /// off or unavailable, not running, or finished. Pure, so the "when does
    /// the row appear" rule is testable without a server.
    ///
    /// Response shape (server-owned): `{"enabled": bool, "unavailable":
    /// null|"not_macos"|"vision_missing"|"no_job", "running": bool, "done":
    /// int, "total": int, "seconds_done": float, "seconds_total": float,
    /// "rate": float|null, "has_screens": bool, "has_page_screens": bool, "available": bool}`.
    static func parse(_ json: [String: Any]) -> ScreenReadingProgress? {
        guard json["enabled"] as? Bool == true,
              json["running"] as? Bool == true,
              let done = (json["done"] as? NSNumber)?.intValue,
              let total = (json["total"] as? NSNumber)?.intValue,
              total > 0, done >= 0, done < total
        else { return nil }
        return ScreenReadingProgress(
            done: done,
            total: total,
            secondsDone: (json["seconds_done"] as? NSNumber)?.doubleValue ?? 0,
            secondsTotal: (json["seconds_total"] as? NSNumber)?.doubleValue ?? 0,
            rate: (json["rate"] as? NSNumber)?.doubleValue
        )
    }

    /// Does this project have a Screens lens to offer? The rail row, ⌘7 and the
    /// View menu row follow the server's answer, `available` — the rule's one
    /// copy is `screens_available` in server/routes/screens.py, which the SPA's
    /// nav reads too. Never re-derived here from the counts. An older serve
    /// without the field answers no.
    static func isAvailable(_ json: [String: Any]) -> Bool {
        json["available"] as? Bool == true
    }
}

/// How far an AutoCode pass has got through a project's quotes: a first apply (the house default
/// after a run that shows screens, or an Apply the researcher pressed), or a running catch-up
/// (re-enabling a codebook codes the quotes it still owes, landing plan D40). Shown on the row as
/// "AutoCode · N of M" (`SubtitleVariant.codingQuotes`), shaped like the screens line, with a ring
/// whose hover × stops it (D38).
///
/// Read from `GET /api/projects/1/autocode/jobs?include_ended=true`. A first apply counts its
/// `processed_quotes` of `total_quotes`, written per batch. A catch-up (a job with a
/// `completed_at`) counts **its own pass**, `catch_up_processed` of `catch_up_total`: the
/// cumulative pair holds every earlier pass, so "101 of 101" would sit there for the whole pass.
/// A job whose count is not below its total is finishing, so it shows nothing (the Signals build
/// that follows takes over).
struct AutoCodeProgress: Equatable {
    /// Quotes answered so far, and in all.
    let done: Int
    let total: Int
    /// The codebook being coded: what the ring's Stop cancels.
    var frameworkID: String = ""

    /// `{"jobs": [{"framework_id", "status", "completed_at", "processed_quotes", "total_quotes",
    /// "catch_up_processed", "catch_up_total", …}]}`, listed by start; the **most recently
    /// started** job that is pending or running and has something left to do. One codebook per
    /// row, so the line, its ring and Stop all name the same run; with two at once, the newer
    /// (lead to confirm). A count past its total (a catch-up whose total was not written) shows
    /// nothing. Pure, so the rule for when the line appears is testable without a server.
    static func parse(_ json: [String: Any]) -> AutoCodeProgress? {
        guard let jobs = json["jobs"] as? [[String: Any]] else { return nil }
        for job in jobs.reversed() {
            guard let status = job["status"] as? String, status == "pending" || status == "running"
            else { continue }
            let catchUp = job["completed_at"] as? String != nil
            guard let done = (job[catchUp ? "catch_up_processed" : "processed_quotes"] as? NSNumber)?.intValue,
                  let total = (job[catchUp ? "catch_up_total" : "total_quotes"] as? NSNumber)?.intValue,
                  total > 0, done >= 0, done < total
            else { continue }
            return AutoCodeProgress(done: done, total: total,
                                    frameworkID: job["framework_id"] as? String ?? "")
        }
        return nil
    }
}

/// A first AutoCode apply that ended without finishing cleanly: stopped, failed, or finished with
/// some batches failed. The row says so in the pipeline run's words (landing plan D13, D23) until
/// the researcher opens the study or starts the codebook again.
///
/// Read from the same `…/autocode/jobs?include_ended=true` answer as `AutoCodeProgress`. Codable
/// because it outlives the server: a study's server is reaped a little after its last window
/// closes, and a failure seen before the reap must still be on the row after it
/// (`AutoCodeLineMemory`, persisted by `ScreenReadingStore`).
struct AutoCodeEndedLine: Codable, Equatable {
    enum Outcome: String, Codable {
        /// The researcher's Stop: "Stopped", no glyph (D23).
        case stopped
        /// The run failed partway: the failure's own label, with its glyph (D23).
        case failed
        /// The run finished with some batches failed: "Partial run", warning glyph (D23).
        case partial
    }

    let outcome: Outcome
    /// `LLMFailureKind` raw value (`bristlenose/llm/failure_classifier.py`), or "" for a Stop or
    /// a failure the classifier did not name.
    let failureKind: String
    let frameworkID: String
    /// The codebook's title, for the popover. Data, not chrome.
    let title: String
    /// Quotes answered and in all, for the partial run's sentence.
    let processed: Int
    let total: Int
    /// Which run this is: the codebook, when the run started, and how it ended. A restart is a new
    /// run with a new key, so a line the researcher has seen is never mistaken for a new one.
    let key: String

    /// Every ended first apply in the answer, in its order (by start). A running job, a clean
    /// finish, and a catch-up (a job with `completed_at` that did not fail as a first apply) are
    /// not ended lines. The route lists only these shapes, but the rule does not rely on it.
    static func parseAll(_ json: [String: Any]) -> [AutoCodeEndedLine] {
        guard let jobs = json["jobs"] as? [[String: Any]] else { return [] }
        return jobs.compactMap { job in
            guard let status = job["status"] as? String,
                  let framework = job["framework_id"] as? String else { return nil }
            let applied = job["completed_at"] as? String != nil
            let failureKind = job["failure_kind"] as? String ?? ""
            let outcome: Outcome
            switch status {
            case "cancelled" where !applied: outcome = .stopped
            case "failed" where !applied: outcome = .failed
            case "completed" where !failureKind.isEmpty: outcome = .partial
            default: return nil
            }
            let started = job["started_at"] as? String ?? ""
            return AutoCodeEndedLine(
                outcome: outcome, failureKind: failureKind, frameworkID: framework,
                title: job["title"] as? String ?? framework,
                processed: (job["processed_quotes"] as? NSNumber)?.intValue ?? 0,
                total: (job["total_quotes"] as? NSNumber)?.intValue ?? 0,
                key: "\(framework)|\(started)|\(status)")
        }
    }

    /// The failures the web chip calls warnings, because waiting fixes them
    /// (`frontend/src/utils/autocodeFailure.ts`). Every other failure is an error: out of credit
    /// and a rejected key above all (D23).
    private static let waitingFixes: Set<String> = ["rate_limited", "server_error", "network"]

    /// The glyph the row draws: none for a Stop (the researcher knows), warning for a partial run
    /// and a failure that waiting fixes, error for the rest.
    var glyphKind: MessageKind? {
        switch outcome {
        case .stopped: return nil
        case .partial: return .warning
        case .failed: return Self.waitingFixes.contains(failureKind) ? .warning : .error
        }
    }

    /// The pipeline's category for a failure kind, so the row says it in the run's words (D13):
    /// "Out of credit", "Provider key issue", … nil for a failure with no category, which reads
    /// "Run failed" as an unnamed run failure does.
    var pipelineCategory: PipelineFailureCategory? {
        switch failureKind {
        case "out_of_credit": return .outOfCredit
        case "invalid_key": return .auth
        case "rate_limited": return .quota
        case "server_error": return .apiServer
        case "network": return .network
        case "model_unavailable": return .modelUnavailable
        case "bad_request": return .apiRequest
        default: return nil
        }
    }

    /// The long sentence the web chip says for this failure (`codebook.autocodeFailure.*`, the
    /// common namespace both surfaces read), for the popover. Keys spelled whole: the orphan gate
    /// reads literals.
    var failureSentenceKey: String {
        switch failureKind {
        case "out_of_credit": return "common.codebook.autocodeFailure.outOfCredit"
        case "rate_limited": return "common.codebook.autocodeFailure.rateLimited"
        case "invalid_key": return "common.codebook.autocodeFailure.invalidKey"
        case "server_error": return "common.codebook.autocodeFailure.serverError"
        case "bad_request": return "common.codebook.autocodeFailure.badRequest"
        case "model_unavailable": return "common.codebook.autocodeFailure.modelUnavailable"
        case "network": return "common.codebook.autocodeFailure.network"
        default: return "common.codebook.autocodeFailure.unknown"
        }
    }

    /// Which of several ended lines the row shows: a failure over a partial run over a Stop; the
    /// earliest-started of equals.
    static func pick(_ lines: [AutoCodeEndedLine]) -> AutoCodeEndedLine? {
        func rank(_ o: Outcome) -> Int {
            switch o {
            case .failed: return 0
            case .partial: return 1
            case .stopped: return 2
            }
        }
        return lines.enumerated().min { a, b in
            (rank(a.element.outcome), a.offset) < (rank(b.element.outcome), b.offset)
        }?.element
    }
}

/// What the row remembers about a project's ended AutoCode runs, apart from its server, so a line
/// survives the server being reaped and the app quitting, and clears when the researcher opens
/// the study or starts the codebook again (landing plan Phase 5).
///
/// - `candidates`: the ended runs the server listed on its last good answer that the researcher
///   has not yet seen. Replaced wholesale by every good answer, so a codebook started again (no
///   longer ended) drops out at once.
/// - `acknowledged`: the keys of runs the researcher has seen by opening the study. Kept only
///   while the server still lists them, so the set cannot grow without bound.
///
/// Pure value type: the rules are table-tested without a store, a server or a window.
struct AutoCodeLineMemory: Codable, Equatable {
    var candidates: [AutoCodeEndedLine] = []
    var acknowledged: Set<String> = []

    /// The line the row shows, if any.
    var line: AutoCodeEndedLine? { AutoCodeEndedLine.pick(candidates) }

    var isEmpty: Bool { candidates.isEmpty && acknowledged.isEmpty }

    /// A good answer from the server: `listed` is every ended run it named.
    mutating func observe(_ listed: [AutoCodeEndedLine]) {
        let keys = Set(listed.map(\.key))
        acknowledged.formIntersection(keys)
        candidates = listed.filter { !acknowledged.contains($0.key) }
    }

    /// The researcher opened the study: a Stop is seen, and clears. A failure and a partial run
    /// are not cleared by being seen: they stay until they are resolved (the codebook started
    /// again or resumed, and the server stops listing them), because a failed run must stay
    /// visible and retryable (owner's rule; Phase 5a review).
    mutating func acknowledge() {
        let seen = candidates.filter { $0.outcome == .stopped }
        acknowledged.formUnion(seen.map(\.key))
        candidates.removeAll { $0.outcome == .stopped }
    }

    /// The server could not list ended runs (a 404: an older serve, or no such project). What was
    /// listed goes, but what the researcher has seen stays seen, so it never comes back.
    mutating func listingUnavailable() {
        candidates = []
    }
}

/// One read of the ended AutoCode runs: what the server listed, or that it could not list them.
enum AutoCodeEndedAnswer: Equatable {
    case listed([AutoCodeEndedLine])
    case unavailable
}

/// What Stop does for a project, wherever it is asked (Project ▸ Stop and ⌘., the row's context
/// menu): the pipeline run when the app can stop one, which wins when both run; else a running
/// AutoCode pass, gated on the run alone and not on which line the row shows (Phase 5a review);
/// else nothing. One decision, so the menu bar, the context menu and the label cannot disagree.
enum StopTarget: Equatable {
    case pipeline
    case autocode(framework: String)
    case none

    static func resolve(pipelineCanStop: Bool, autocode: AutoCodeProgress?,
                        stopping: Bool) -> StopTarget {
        if pipelineCanStop { return .pipeline }
        if let autocode, !autocode.frameworkID.isEmpty, !stopping {
            return .autocode(framework: autocode.frameworkID)
        }
        return .none
    }

    /// Whether Project ▸ Stop carries ⌘. in this state. Not for AutoCode (lead's call, pending
    /// the owner): the web report binds ⌘. to "toggle both sidebars" on the Quotes lens, where
    /// AutoCode runs, so ⌘. there would stop the run when the researcher meant the sidebars.
    /// The pipeline's Stop Analysis keeps it, as before.
    var takesCommandPeriod: Bool { if case .autocode = self { false } else { true } }

    /// The menu item's words: "Stop Analysis" for the run, "Stop AutoCode" for AutoCode (the
    /// owner's option B, `docs/mockups/autocode-mac-popup.html`). Keys spelled whole for the
    /// orphan gate.
    var labelKey: String {
        switch self {
        case .autocode: return "desktop.menu.project.stopAutoCode"
        case .pipeline, .none: return "desktop.menu.project.stopAnalysis"
        }
    }
}

/// Per-project serve background progress, for the sidebar: the screen-reading job's
/// (`progress`, `available`), a running AutoCode pass's (`autocode`), and an ended first apply's
/// line (`autocodeEnded`, which outlives the server).
///
/// **Its own `ObservableObject`, never a field on `ServeInstance`.** A value
/// published through `ServeInstance` reaches `ServeManager` and then
/// `ServeFleet`, whose `objectWillChange` every window observes; republishing
/// on each poll tick that way collapsed an open Window menu on 20 Sep 2026.
/// So the poll writes here (the `PipelineLiveData` split, for the same
/// reason), and only on change: an unchanged tick publishes nothing.
@MainActor
final class ScreenReadingStore: ObservableObject {
    static let shared = ScreenReadingStore(defaults: .standard)

    @Published private(set) var progress: [UUID: ScreenReadingProgress] = [:]

    /// An AutoCode pass in each project, when one is running (`AutoCodeProgress`).
    @Published private(set) var autocode: [UUID: AutoCodeProgress] = [:]

    /// The ended AutoCode line each project's row shows (`AutoCodeEndedLine`), derived from
    /// `memory`. Survives the project's server: only a good answer, an open or a removal moves it.
    @Published private(set) var autocodeEnded: [UUID: AutoCodeEndedLine] = [:]

    /// What each project remembers about its ended runs. Persisted under `Self.endedLinesKey`
    /// when the store has `defaults`, so a failure line outlives a reap and a quit.
    private var memory: [UUID: AutoCodeLineMemory] = [:]

    /// Where `memory` is persisted: `UserDefaults` under this key, one JSON object keyed by the
    /// project's id. Nil for a store with no `defaults` (every test's, unless it passes a suite).
    private let defaults: UserDefaults?
    static let endedLinesKey = "autocodeEndedLines"

    /// Stops a project's running AutoCode pass. Set by `ServeFleet`, which owns the servers; call
    /// `stopAutoCode(_:framework:)`, which acknowledges the click first.
    var onStopAutoCode: ((UUID, String) -> Void)?

    /// The codebook a Stop was asked of, per project, until the run's count goes: the row says
    /// "Stopping…" and its ring loses the × at once (the immediate acknowledgement a copy's cancel
    /// gives), rather than waiting for the next read.
    @Published private(set) var autocodeStopping: [UUID: String] = [:]

    /// Stop `project`'s running AutoCode pass on `framework`: the ring's hover ×, the row menu's
    /// Stop AutoCode and Project ▸ Stop AutoCode (⌘.) all come here.
    func stopAutoCode(_ project: UUID, framework: String) {
        guard !framework.isEmpty, autocodeStopping[project] == nil else { return }
        autocodeStopping[project] = framework
        onStopAutoCode?(project, framework)
    }

    /// The cancel request found no server or no answer: the run is still going, so the × comes
    /// back. (A refusal because it had already ended clears with its count.)
    func autoCodeStopFailed(for project: UUID) {
        if autocodeStopping[project] != nil { autocodeStopping[project] = nil }
    }

    init(defaults: UserDefaults? = nil) {
        self.defaults = defaults
        guard let data = defaults?.data(forKey: Self.endedLinesKey),
              let stored = try? JSONDecoder().decode([String: AutoCodeLineMemory].self, from: data)
        else { return }
        for (key, value) in stored {
            guard let id = UUID(uuidString: key) else { continue }
            memory[id] = value
            if let line = value.line { autocodeEnded[id] = line }
        }
    }

    /// The projects that have a Screens lens to offer
    /// (`ScreenReadingProgress.isAvailable`). Windows mirror their own
    /// project's membership onto the bridge, which is what puts the Screens
    /// row on the rail and ⌘7 in the View menu.
    @Published private(set) var available: Set<UUID> = []

    /// Write `value` for `project` — and publish only if it differs. `nil`
    /// clears the row.
    func set(_ value: ScreenReadingProgress?, for project: UUID) {
        guard progress[project] != value else { return }
        progress[project] = value
    }

    /// Write a running AutoCode pass's `value` for `project`; publishes only on change, and `nil`
    /// clears the row.
    func setAutoCode(_ value: AutoCodeProgress?, for project: UUID) {
        // A Stop's "Stopping…" lasts until the run it stopped is no longer the one counting.
        if let stopping = autocodeStopping[project], value?.frameworkID != stopping {
            autocodeStopping[project] = nil
        }
        guard autocode[project] != value else { return }
        autocode[project] = value
    }

    /// The server's good answer for `project`: every ended AutoCode run it lists. Not called when
    /// there is no running server, so a reap leaves the line where it was.
    func noteAutoCodeEnded(_ listed: [AutoCodeEndedLine], for project: UUID) {
        var m = memory[project] ?? AutoCodeLineMemory()
        m.observe(listed)
        commit(m, for: project)
    }

    /// The server answered that it cannot list ended runs (404): drop what was listed, keep what
    /// was seen (`AutoCodeLineMemory.listingUnavailable`).
    func noteAutoCodeUnavailable(for project: UUID) {
        guard var m = memory[project] else { return }
        m.listingUnavailable()
        commit(m, for: project)
    }

    /// The researcher opened `project`: its "Stopped" line is seen, and clears; a failure stays
    /// until it is resolved.
    func acknowledgeAutoCode(for project: UUID) {
        guard var m = memory[project] else { return }
        m.acknowledge()
        commit(m, for: project)
    }

    /// `project` left the sidebar: nothing of it is kept.
    func forgetAutoCode(for project: UUID) {
        guard memory[project] != nil else { return }
        commit(AutoCodeLineMemory(), for: project)
    }

    /// Store `m`, publish the line only on change, and persist only on change.
    private func commit(_ m: AutoCodeLineMemory, for project: UUID) {
        let before = memory[project] ?? AutoCodeLineMemory()
        memory[project] = m.isEmpty ? nil : m
        if autocodeEnded[project] != m.line { autocodeEnded[project] = m.line }
        guard before != m, let defaults else { return }
        let stored = Dictionary(uniqueKeysWithValues: memory.map { ($0.key.uuidString, $0.value) })
        if stored.isEmpty {
            defaults.removeObject(forKey: Self.endedLinesKey)
        } else if let data = try? JSONEncoder().encode(stored) {
            defaults.set(data, forKey: Self.endedLinesKey)
        }
    }

    /// Record whether `project` has a Screens lens — publishing only on change,
    /// for the same reason as `set`.
    func setAvailable(_ isAvailable: Bool, for project: UUID) {
        guard available.contains(project) != isAvailable else { return }
        if isAvailable { available.insert(project) } else { available.remove(project) }
    }
}
