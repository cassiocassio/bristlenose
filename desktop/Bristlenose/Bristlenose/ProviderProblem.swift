import Foundation

// The decisions behind the title-bar provider-problem pill, pure and testable.
// `ProviderProblemModel` holds the state and `ProviderProblemPill` draws it; the
// argument for every rule here is `docs/mockups/provider-problem-surface.html`.

/// What the pill can tell the researcher. Both are an *observed* refusal from
/// the provider: it answered, and said no. Network failures are a different
/// question (can we tell offline from blocked from an outage?) and are not here.
enum ProviderProblemCondition: String, Codable, Equatable, CaseIterable {
    case keyRejected
    case outOfCredit

    /// The glyph and tint come from the existing five-kind vocabulary; the words
    /// say which condition. No glyph of its own.
    var kind: MessageKind {
        switch self {
        case .keyRejected: return .error
        case .outOfCredit: return .warning
        }
    }

    /// The cached verdict that stands for this condition. The pill is held to
    /// it: when the verdict for the key no longer says this, the pill goes.
    var verdict: LLMValidator.CachedVerdict {
        switch self {
        case .keyRejected: return .invalid
        case .outOfCredit: return .outOfCredit
        }
    }

    /// From the failure kinds the sidecar posts over the bridge
    /// (`LLMFailureKind` in `bristlenose/llm/failure_classifier.py`; they agree
    /// on these strings by convention, not by contract).
    static func fromLLMFailureKind(_ raw: String?) -> ProviderProblemCondition? {
        switch raw {
        case "out_of_credit": return .outOfCredit
        case "invalid_key": return .keyRejected
        default: return nil
        }
    }

    /// From a finished run's failure category. A rejected key counts only when
    /// the category came from the run's structured cause: the stderr fallback
    /// matches `401` and `authentication` anywhere in the tail, which is a guess
    /// (it once called a preflight line a failed transcription), and a guess
    /// must not light a pill that sits over every project.
    static func fromRun(category: PipelineFailureCategory, structured: Bool)
        -> ProviderProblemCondition? {
        switch category {
        case .outOfCredit: return .outOfCredit
        case .auth: return structured ? .keyRejected : nil
        default: return nil
        }
    }
}

/// How loud the pill is. Not a timer: the model evaluates it when it refreshes
/// (launch, window activation, a new refusal), so nothing changes while the
/// person is looking at the toolbar.
enum ProviderProblemStage: String, Equatable {
    /// A tinted capsule, for the first minutes after a refusal.
    case loud
    /// The plain capsule.
    case settled
    /// The bare glyph, a day on. Nothing is removed; the glyph still opens it.
    case collapsed
}

/// What is kept between launches: the last refusal, and whether it was hidden.
struct ProviderProblemRecord: Codable, Equatable {
    var provider: String
    var condition: ProviderProblemCondition
    var firstSeen: Date
    var lastRefusal: Date
    var dismissed: Bool
}

enum ProviderProblemRules {
    /// "When it first occurs it needs to be prominent."
    static let loudFor: TimeInterval = 15 * 60
    /// "A day later" it collapses to the glyph.
    static let settledFor: TimeInterval = 24 * 60 * 60

    /// The stage at `now`, or nil when the researcher has hidden it.
    static func stage(of record: ProviderProblemRecord, now: Date) -> ProviderProblemStage? {
        if record.dismissed { return nil }
        let age = now.timeIntervalSince(record.firstSeen)
        if age < loudFor { return .loud }
        if age < settledFor { return .settled }
        return .collapsed
    }

    /// The record after a refusal.
    ///
    /// - A different provider or condition is news: a fresh, loud record.
    /// - The same condition again, from something the researcher started (a run
    ///   they asked for): they are trying again and meeting the same wall, so it
    ///   is loud again and no longer hidden.
    /// - The same condition again, from something incidental (a background
    ///   refresh, an edit that needed a few cents): nothing to say that wasn't
    ///   said. A hidden pill stays hidden; the clock is not restarted. Months of
    ///   edits on an empty account must not bring the pill back each time.
    static func applying(
        refusalOf condition: ProviderProblemCondition,
        provider: String,
        explicit: Bool,
        to existing: ProviderProblemRecord?,
        now: Date
    ) -> ProviderProblemRecord {
        let fresh = ProviderProblemRecord(
            provider: provider, condition: condition,
            firstSeen: now, lastRefusal: now, dismissed: false)
        guard let existing,
              existing.provider == provider,
              existing.condition == condition
        else { return fresh }
        if explicit { return fresh }
        var kept = existing
        kept.lastRefusal = now
        return kept
    }

    /// Whether the record is still true of the key in use: the key's cached
    /// verdict must still say what the record says. A new key (no verdict for
    /// it), a re-validation that came back good, or a run that worked all make
    /// it false.
    static func holds(_ record: ProviderProblemRecord,
                      verdictForItsKey verdict: LLMValidator.CachedVerdict?) -> Bool {
        verdict == record.condition.verdict
    }
}

/// What each condition says, and which buttons it offers.
enum ProviderProblemAction: Hashable {
    case switchProvider
    case addFunds
    case openSettings
}

struct ProviderProblemPresentation: Equatable {
    let condition: ProviderProblemCondition

    var kind: MessageKind { condition.kind }

    /// The shipped out-of-credit keys keep their `%@` placeholder; the new ones
    /// use `{{provider}}`. `usesPrintfProviderFormat` says which, so the view
    /// need not know the history.
    var pillKey: String {
        switch condition {
        case .outOfCredit: return "desktop.outOfCredit.pill"
        case .keyRejected: return "desktop.providerProblem.keyRejected.pill"
        }
    }

    var titleKey: String {
        switch condition {
        case .outOfCredit: return "desktop.outOfCredit.title"
        case .keyRejected: return "desktop.pipeline.failure.auth"
        }
    }

    /// Line 2: the remedy, as the shipped out-of-credit popover has it.
    var bodyKey: String {
        switch condition {
        case .outOfCredit: return "desktop.outOfCredit.body"
        case .keyRejected: return "desktop.providerProblem.keyRejected.body"
        }
    }

    var usesPrintfProviderFormat: Bool {
        switch condition {
        case .outOfCredit: return true
        case .keyRejected: return false
        }
    }

    var kindWordKey: String {
        switch kind {
        case .error: return "desktop.providerProblem.kind.error"
        default: return "desktop.providerProblem.kind.warning"
        }
    }

    /// In reading order; the last is the default action. No Hide button: the
    /// pill's ✕ is the dismiss, so the popover keeps to the buttons the shipped
    /// one had. "Switch provider…" is offered only where it is a different act
    /// from the primary one; for a rejected key both would open the same pane.
    var actions: [ProviderProblemAction] {
        switch condition {
        case .outOfCredit: return [.switchProvider, .addFunds]
        case .keyRejected: return [.openSettings]
        }
    }
}
