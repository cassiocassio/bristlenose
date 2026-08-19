import Foundation

/// Swift mirror of the v5 `PipelineSummary` contract emitted by
/// `bristlenose/events.py` on terminus events (`run_completed` / `run_failed` /
/// `run_cancelled`). The schema lives in
/// `tests/fixtures/pipeline-summary-contract.json` and both sides round-trip
/// every scenario in tests. **Schema-additive** — new optional fields on the
/// wire are absorbed; do not rename or repurpose existing ones without
/// coordinating with `bristlenose/events.py` and bumping the fixture version.
struct PipelineSummary: Codable, Equatable {
    /// Stages 1-2. Files declined by format, and files accepted and then found
    /// unreadable — one bucket, because to the researcher they are one event:
    /// a participant missing from the findings.
    ///
    /// **A non-empty `failed` here does not mean the run failed.** It is
    /// counted by `totalFailureCount`, which gates `.completedPartial` — which
    /// is correct and deliberate: a run that produced 38 sessions out of 58
    /// files IS partial, and saying so is the whole point.
    var ingest: StageOutcome?
    var transcripts: StageOutcome?
    var topics: StageOutcome?
    var quotes: StageOutcome?
    var themes: StageOutcome?

    /// All buckets in spec-order. Used by callers walking failures across the
    /// whole summary (dominant-category counting, plaintext rendering).
    var allBuckets: [(name: BucketName, outcome: StageOutcome)] {
        [
            (.ingest, ingest),
            (.transcripts, transcripts),
            (.topics, topics),
            (.quotes, quotes),
            (.themes, themes),
        ].compactMap { name, outcome in outcome.map { (name, $0) } }
    }

    /// Total session-failure count across every bucket. Used to gate the
    /// `.completedPartial` derivation (>0 → partial; 0 → clean → `.ready`).
    var totalFailureCount: Int {
        allBuckets.reduce(0) { $0 + $1.outcome.failed.count }
    }

    /// Failures across every bucket. Used by `dominantCategory` and by the
    /// plaintext renderer; preserves spec-order (transcripts → topics →
    /// quotes → themes) so the output is deterministic.
    var allFailures: [SessionFailure] {
        allBuckets.flatMap { $0.outcome.failed }
    }

    /// Spec-locked precedence chain for pill-label selection
    /// (`docs/design-pipeline-diagnostic-popover.md`):
    /// AUTH > OUT_OF_CREDIT > MISSING_BINARY > QUOTA > NETWORK > UNKNOWN.
    /// Ties prefer the non-retryable cause — `outOfCredit` sits beside `auth`
    /// (both are account-level and terminal until the user acts out-of-band),
    /// and above `quota`, which is a transient throttle worth retrying.
    /// Categories not in the chain still appear in the popover with their real
    /// labels — this only selects the single pill string.
    static let pillPrecedence: [CauseCategory] = [
        .auth, .outOfCredit, .missingBinary, .quota, .network, .unknown,
    ]

    /// Returns the dominant category for the pill. Highest failure count
    /// wins; ties broken by `pillPrecedence`; categories outside the chain
    /// collapse to `.unknown`. Returns `.unknown` when there are no failures.
    func dominantCategory() -> CauseCategory {
        var counts: [CauseCategory: Int] = [:]
        for failure in allFailures {
            let key = Self.pillPrecedence.contains(failure.cause.category)
                ? failure.cause.category
                : .unknown
            counts[key, default: 0] += 1
        }
        guard !counts.isEmpty else { return .unknown }
        // Highest count first; ties resolved by pillPrecedence order.
        let maxCount = counts.values.max() ?? 0
        for category in Self.pillPrecedence where counts[category] == maxCount {
            return category
        }
        return .unknown
    }

    enum BucketName: String {
        case ingest, transcripts, topics, quotes, themes

        /// What the researcher reads. The popover used to render
        /// `rawValue.capitalized`, which happened to be legible for four
        /// nouns it was never asked to translate — and then `ingest` arrived,
        /// which is our word for it, not theirs. "Files" is the word already
        /// on the empty-project pane and in the unanalysed sheet.
        var label: String {
            switch self {
            case .ingest:      return "Files"
            case .transcripts: return "Transcripts"
            case .topics:      return "Topics"
            case .quotes:      return "Quotes"
            case .themes:      return "Themes"
            }
        }
    }
}

/// One stage's outcome for one run, as emitted in `PipelineSummary`.
struct StageOutcome: Codable, Equatable {
    var attempted: Int
    var succeeded: Int
    /// Wall-clock this stage spent on *this* run. **Optional, and it must stay
    /// optional**: Python declares `duration_ms: int | None` and writes the
    /// terminus with `exclude_none=False`, so a stage that was present but
    /// didn't run (every entry a cache hit, or the stage was skipped) puts a
    /// literal `null` on the wire — distinct from `0`, which would mean "ran,
    /// instantaneously".
    ///
    /// This was declared non-optional until 29 Jul 2026, which made `null` fail
    /// to decode and took the **entire** `PipelineSummary` with it — so a run
    /// with any fully-cached stage silently produced no diagnostic at all. Every
    /// contract-fixture scenario happened to carry a real duration, so the
    /// round-trip tests flattered it; `run_completed_cached_stage` now locks the
    /// null case.
    var durationMs: Int?
    var failed: [SessionFailure]

    enum CodingKeys: String, CodingKey {
        case attempted, succeeded
        case durationMs = "duration_ms"
        case failed
    }
}

/// A single session-level failure inside a `StageOutcome.failed` list.
///
/// **Overflow placeholder shape**: when STAGE_FAILED_MAX (=10 on the wire)
/// truncation kicks in, an extra entry is appended with `session_id == nil`
/// AND `cause.message` prefixed by `"... and "`. Detect via
/// `isOverflowPlaceholder` — render as a single muted summary row, never as
/// an N+1th session.
struct SessionFailure: Codable, Equatable {
    var sessionId: String?
    /// Basename of the input file this failure is about, when there is one.
    /// Mirrors Python `StageFailure.source_file`.
    ///
    /// `sessionId` alone can't identify the file for failures that happen
    /// *before* a session exists — an unreadable or never-materialised recording
    /// fails at probe/ingest and never gets a session id. Load-bearing for the
    /// sidebar: the row subtracts failed basenames from the `+N unanalysed`
    /// drift (which is basename-keyed), so without this the same file is
    /// reported twice, once as waiting and once as failed.
    var sourceFile: String?
    var cause: Cause

    enum CodingKeys: String, CodingKey {
        case sessionId = "session_id"
        case sourceFile = "source_file"
        case cause
    }

    var isOverflowPlaceholder: Bool {
        sessionId == nil && cause.message?.hasPrefix("... and ") == true
    }
}

/// Mirror of `bristlenose/events.py::Cause`. Field-by-field. The mirror in
/// `EventLogReader.Cause` is a partial subset for terminus-level cause —
/// this struct is the full per-session shape carried inside `StageOutcome`.
struct Cause: Codable, Equatable {
    var category: CauseCategory
    var code: String?
    var message: String?
    var provider: String?
    var stage: String?
    var sessionId: String?
    var exitCode: Int?
    var signal: Int?
    var signalName: String?

    enum CodingKeys: String, CodingKey {
        case category, code, message, provider, stage
        case sessionId = "session_id"
        case exitCode = "exit_code"
        case signal
        case signalName = "signal_name"
    }
}

/// Swift mirror of `bristlenose/events.py::CauseCategoryEnum`. Raw values are
/// snake_case — keep aligned with the Python enum so JSON round-trips.
enum CauseCategory: String, Codable, Equatable, CaseIterable {
    case userSignal = "user_signal"
    case auth
    /// Billing exhausted — terminal until top-up. Distinct from `quota`
    /// (transient rate-limit). Mirrors Python `CauseCategoryEnum.OUT_OF_CREDIT`.
    case outOfCredit = "out_of_credit"
    /// Transient rate-limit / throttling. Billing exhaustion is `outOfCredit`.
    case quota
    case apiRequest = "api_request"
    case apiServer = "api_server"
    case network
    case whisper
    case missingDep = "missing_dep"
    case missingInput = "missing_input"
    case missingBinary = "missing_binary"
    case disk
    /// Model output cap hit even after splitting. Mirrors Python
    /// `CauseCategoryEnum.OUTPUT_TRUNCATED` — was missing here, so an
    /// `output_truncated` cause failed to decode the whole summary.
    case outputTruncated = "output_truncated"
    /// A cloud placeholder never materialised — the file was still downloading,
    /// not damaged. Mirrors Python `CauseCategoryEnum.CLOUD_FETCH`. **Must not
    /// collapse with a probe failure**: opposite remedies (wait / check the
    /// provider vs re-export the recording), and mislabelling a slow download as
    /// a corrupt file is the defect this category exists to end.
    case cloudFetch = "cloud_fetch"
    /// One input file isn't in the report — declined by format, or accepted and
    /// then unreadable. Both halves share this category because they share a
    /// consequence for the researcher: a participant missing from the findings.
    /// The specific reason rides in `Cause.message`. Mirrors Python
    /// `CauseCategoryEnum.UNUSABLE_INPUT` (`bristlenose/refusals.py`).
    case unusableInput = "unusable_input"
    case unknown

    /// Decode an unrecognised category as `.unknown` instead of throwing.
    ///
    /// `outputTruncated` above records what happens without this, in the past
    /// tense: it "was missing here, so an `output_truncated` cause failed to
    /// decode **the whole summary**". That is the shape of the bug — the
    /// category sits inside `Cause` inside `StageFailure` inside the summary,
    /// so one unrecognised word costs every per-stage row on the event. The
    /// fix then was to add the missing case; adding cases does not prevent the
    /// next one, and this does. `unusable_input` would have done it again to
    /// any build shipped before Aug 2026.
    ///
    /// `CaseIterable` conformance is preserved — the synthesised `allCases`
    /// is unaffected by a custom decoder.
    init(from decoder: Decoder) throws {
        let raw = try decoder.singleValueContainer().decode(String.self)
        self = CauseCategory(rawValue: raw) ?? .unknown
    }
}
