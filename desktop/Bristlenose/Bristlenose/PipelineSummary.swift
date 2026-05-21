import Foundation

/// Swift mirror of the v5 `PipelineSummary` contract emitted by
/// `bristlenose/events.py` on terminus events (`run_completed` / `run_failed` /
/// `run_cancelled`). The schema lives in
/// `tests/fixtures/pipeline-summary-contract.json` and both sides round-trip
/// every scenario in tests. **Schema-additive** — new optional fields on the
/// wire are absorbed; do not rename or repurpose existing ones without
/// coordinating with `bristlenose/events.py` and bumping the fixture version.
struct PipelineSummary: Codable, Equatable {
    var transcripts: StageOutcome?
    var topics: StageOutcome?
    var quotes: StageOutcome?
    var themes: StageOutcome?

    /// All buckets in spec-order. Used by callers walking failures across the
    /// whole summary (dominant-category counting, plaintext rendering).
    var allBuckets: [(name: BucketName, outcome: StageOutcome)] {
        [
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
    /// (`docs/design-pipeline-diagnostic-popover.md` line 164):
    /// AUTH > MISSING_BINARY > QUOTA > NETWORK > UNKNOWN. Categories not in
    /// the chain still appear in the popover with their real labels — this
    /// only selects the single pill string.
    static let pillPrecedence: [CauseCategory] = [
        .auth, .missingBinary, .quota, .network, .unknown,
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
        case transcripts, topics, quotes, themes
    }
}

/// One stage's outcome for one run, as emitted in `PipelineSummary`.
struct StageOutcome: Codable, Equatable {
    var attempted: Int
    var succeeded: Int
    var durationMs: Int
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
    var cause: Cause

    enum CodingKeys: String, CodingKey {
        case sessionId = "session_id"
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
    case quota
    case apiRequest = "api_request"
    case apiServer = "api_server"
    case network
    case whisper
    case missingDep = "missing_dep"
    case missingInput = "missing_input"
    case missingBinary = "missing_binary"
    case disk
    case unknown
}
