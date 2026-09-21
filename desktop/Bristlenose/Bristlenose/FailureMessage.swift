import Foundation

/// A failure sentence that may be **ours** or **theirs**.
///
/// Failures are a mix. Some are our words about our own state — "Bristlenose
/// hasn't been set up with a Zoom client ID yet", "Not enough disk space to
/// finish" — and those want a key. Others carry someone else's own words, and
/// Microsoft's "User declined to consent" is already more precise than anything
/// we would write; `TeamsOAuth` says so at the site. Replacing a provider's
/// specific reason with our generic translated one is the loss this codebase
/// paid back once already, in the cloud-import download verdicts.
///
/// So: `key` when the sentence is ours, `nil` when it is a passthrough. `english`
/// is always populated, because `LocalizedError.errorDescription` reaches logs and
/// bug reports and stays English there by decision
/// (`docs/design-i18n.md` §"Which surfaces are targets").
///
/// **Why a type and not a resolved `String`.** Resolving the sentence where the
/// failure is *constructed* pins it to the language in force at that moment —
/// failure class 6 in `docs/i18n-defects.md`. The producers here cannot resolve
/// it correctly even if they wanted to: the OAuth enums and `PipelineRunner`'s
/// classifier are not views and have no `I18n`. Carrying the key plus its
/// variables lets the producer capture the *facts* (which provider, which
/// refusal) while the view supplies the *language*, so switching locale
/// re-renders a failure that is already on screen.
///
/// This is the same shape as `CloudFetchFailure`, `PipelineFailureCategory`,
/// `CopyError.localeKey` and `MiroAPI.APIError.localeKey` — a discriminator
/// travels, the view resolves it. The difference is only that those name a case
/// and this one carries an escape hatch for words that were never ours.
struct FailureMessage: Equatable, Sendable {
    /// A locale key, or nil for a passthrough of someone else's words.
    let key: String?
    /// Substitutions for the key's `{{placeholders}}`, captured where the facts
    /// are known. Ignored for a passthrough.
    let vars: [String: String]
    /// What the log gets, and what the UI falls back to if a key ever goes missing.
    let english: String

    init(key: String? = nil, vars: [String: String] = [:], english: String) {
        self.key = key
        self.vars = vars
        self.english = english
    }

    /// Someone else's own sentence, passed through untouched.
    static func passthrough(_ text: String) -> FailureMessage {
        FailureMessage(english: text)
    }

    /// Resolve for display. `english` is the fallback, never a crash: a key that
    /// has gone missing must degrade to a true English sentence rather than
    /// render raw on a researcher's screen.
    @MainActor
    func resolved(_ i18n: I18n) -> String {
        guard let key else { return english }
        let value = vars.isEmpty ? i18n.t(key) : i18n.t(key, vars)
        return value == key ? english : value
    }
}

// MARK: - The sentences

extension FailureMessage {
    /// One-liner for a failure category, as a key the view resolves.
    ///
    /// When `provider` is supplied, LLM-related categories name it ("Claude
    /// rejected the request.") — the cause classifier can't always recover a
    /// structured message, and a named provider is the difference between an
    /// actionable summary and a shrug. When it isn't, the `…Generic` sibling
    /// says "the AI provider" in the locale's own words. Non-LLM categories
    /// (disk, whisper, …) ignore `provider` and have no sibling.
    ///
    /// **Two keys rather than one with a fallback noun.** Substituting a generic
    /// noun into a slot shaped for a brand name only works in English. The
    /// translators of `desktop.outOfCredit.title` restructured around `%@` to
    /// keep it nominative — Finnish "Palvelun %@ saldo on lopussa", Russian "На
    /// счету %@ закончились средства" — and a phrase dropped into that slot
    /// needs the genitive those sentences can't give it. Each sibling is written
    /// whole instead, so both read correctly in every language.
    ///
    /// `english` carries the same sentence resolved, because it is what the log
    /// and any bug report get, and those stay English by decision.
    static func failure(
        for category: PipelineFailureCategory,
        provider: LLMProvider? = nil
    ) -> FailureMessage {
        let name = provider?.displayName
        let named = category.namesProvider && name != nil
        let leaf = category.localeLeaf + (category.namesProvider && !named ? "Generic" : "")
        let vars = named ? ["provider": name!] : [:]
        return FailureMessage(
            key: "desktop.pipeline.failure." + leaf,
            vars: vars,
            english: englishSentence(forLeaf: leaf, vars: vars)
        )
    }

    /// The English of every `desktop.pipeline.failure.*` value, verbatim.
    ///
    /// This is what the log and the "Copy error details" payload get, and what
    /// the UI falls back to if a key ever goes missing — all three stay English
    /// by decision (`docs/design-i18n.md` §"Which surfaces are targets").
    ///
    /// A table rather than a `switch` so the duplication is *checkable*: it is a
    /// second copy of the `en` locale file, and a reworded sentence that landed
    /// in only one of them is failure class 3 with nothing to report it.
    /// `tests/test_pipeline_failure_keys.py` asserts the two are equal, key for
    /// key, so the copy cannot drift silently.
    static let englishFailureSentences: [String: String] = [
        "stranded": "Analysis stopped unexpectedly.",
        "launchFailed": "Couldn't start the analysis. {{reason}}",
        "auth": "Your {{provider}} key was rejected.",
        "authGeneric": "Your API key was rejected.",
        "outOfCredit": "{{provider}} is out of credit.",
        "outOfCreditGeneric": "Your AI provider account is out of credit.",
        "network": "Couldn't reach {{provider}}. Check your connection.",
        "networkGeneric": "Couldn't reach the AI provider. Check your connection.",
        "quota": "{{provider}} rate limit reached. Try again soon.",
        "quotaGeneric": "Rate limit reached. Try again soon.",
        "apiRequest": "{{provider}} rejected the request.",
        "apiRequestGeneric": "The AI provider rejected the request.",
        "apiServer": "{{provider}} is unavailable. Try again shortly.",
        "apiServerGeneric": "The AI provider is unavailable. Try again shortly.",
        "outputTruncated": "This session is too dense for {{provider}}'s output limit. Try a model with a larger output, or split the recording.",
        "outputTruncatedGeneric": "This session is too dense for the model's output limit. Try a model with a larger output, or split the recording.",
        "disk": "Not enough disk space.",
        "whisper": "Transcription failed — the speech model didn't load.",
        "userSignal": "Run was stopped.",
        "missingDep": "Setup needed — a required tool isn't installed.",
        "missingInput": "A required input file is missing.",
        "missingBinary": "FFmpeg couldn't be found.",
        "outputExists": "Already analysed — re-analysing would replace the existing results.",
        "unusableInput": "Some files couldn't be analysed.",
        "unknown": "Something went wrong during analysis.",
    ]

    /// A failure that belongs to a *moment* in the run rather than to a
    /// classified cause — the spawn threw, or the process died without writing a
    /// terminus. Both happen before there is a cause to classify, so they carry
    /// their own leaf and `PipelineFailureCategory` stays `.unknown`.
    /// `tests/test_pipeline_failure_keys.py` lists them as `_MOMENT_KEYS`.
    static func moment(_ leaf: String, vars: [String: String] = [:]) -> FailureMessage {
        FailureMessage(
            key: "desktop.pipeline.failure." + leaf,
            vars: vars,
            english: englishSentence(forLeaf: leaf, vars: vars)
        )
    }

    /// `englishFailureSentences[leaf]` with `{{provider}}` filled in. Falls back
    /// to the leaf rather than trapping — a missing entry must not take out a
    /// failure report, which is the one moment the app is already in trouble.
    static func englishSentence(forLeaf leaf: String, vars: [String: String]) -> String {
        guard var value = englishFailureSentences[leaf] else { return leaf }
        for (name, replacement) in vars {
            value = value.replacingOccurrences(of: "{{\(name)}}", with: replacement)
        }
        return value
    }
}
