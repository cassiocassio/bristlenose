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
    ///
    /// Billing is admitted from stderr as well, deliberately and not by oversight:
    /// its patterns are provider-specific strings (`insufficient_quota`, "credit
    /// balance is too low") and the run's own preflight sentence, which is itself
    /// a refused call. The asymmetry is the specificity of the patterns.
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
    /// The fingerprint of the key the refusal was about. A record is about one
    /// key: when the key in use changes, the record is no longer true of
    /// anything, whatever a Settings check says about the new one. Optional so a
    /// record written before this field existed still decodes.
    var keyFingerprint: String? = nil
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

    /// Whether a refusal is news, which is when it is announced to VoiceOver:
    /// the first of its kind, a different condition or provider, or a refused run.
    /// An incidental repeat of what is already known is not. The same test as
    /// `applying` uses to decide the record starts afresh, kept in one place so
    /// the two cannot drift.
    static func isNews(
        refusalOf condition: ProviderProblemCondition, provider: String, explicit: Bool,
        keyFingerprint: String? = nil, existing: ProviderProblemRecord?
    ) -> Bool {
        guard let existing, existing.provider == provider, existing.condition == condition
        else { return true }
        // The same refusal, but about a different key: a different matter.
        if let was = existing.keyFingerprint, let now = keyFingerprint, was != now { return true }
        return explicit
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
        keyFingerprint: String? = nil,
        to existing: ProviderProblemRecord?,
        now: Date
    ) -> ProviderProblemRecord {
        let fresh = ProviderProblemRecord(
            provider: provider, condition: condition,
            firstSeen: now, lastRefusal: now, dismissed: false, keyFingerprint: keyFingerprint)
        guard let existing,
              !isNews(refusalOf: condition, provider: provider, explicit: explicit,
                      keyFingerprint: keyFingerprint, existing: existing)
        else { return fresh }
        var kept = existing
        kept.lastRefusal = now
        return kept
    }

    /// Whether the record is still true of the key in use: the key's cached
    /// verdict must still say what the record says. A new key (no verdict for
    /// it) or a re-validation that came back good makes it false; so does a run
    /// that worked (`ProviderProblemModel.noteRunSucceeded` drops the record).
    ///
    /// **One exception:** a good result does not cure *out of credit* for a
    /// provider whose Settings check cannot see credit. ChatGPT's check is a
    /// free model-list request that returns 200 for a bankrupt key, so opening
    /// Settings would otherwise wipe the pill (and the hidden state) with the
    /// account still empty. There only a run that worked is a cure.
    static func holds(_ record: ProviderProblemRecord,
                      verdictForItsKey verdict: LLMValidator.CachedVerdict?,
                      settingsCheckSeesCredit: Bool = true) -> Bool {
        if verdict == .ok, record.condition == .outOfCredit, !settingsCheckSeesCredit {
            return true
        }
        return verdict == record.condition.verdict
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

    /// The pill's words, in the researcher's language.
    @MainActor
    func pillText(provider: String, i18n: I18n) -> String {
        usesPrintfProviderFormat
            ? String(format: i18n.t(pillKey), provider)
            : i18n.t(pillKey, ["provider": provider])
    }

    /// Line 1 of the popover: the state. Also what is announced and what
    /// VoiceOver reads as the pill's label.
    @MainActor
    func title(provider: String, i18n: I18n) -> String {
        usesPrintfProviderFormat
            ? String(format: i18n.t(titleKey), provider)
            : i18n.t(titleKey, ["provider": provider])
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

extension LLMProvider {
    /// Whether a Settings validation of this provider's key is a call that fails
    /// on an empty account. Claude's is a billed one-token request, so it sees
    /// the credit refusal. ChatGPT's, Gemini's and Azure's are free list calls and
    /// cannot (the Python classifier can still call a bare 402 "out of credit" for
    /// any of them, so a record is reachable for each). Deliberately all four, not
    /// a side effect of the one-liner.
    var settingsCheckSeesCredit: Bool { self == .claude }
}
