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
        return keyed(
            "desktop.pipeline.failure." + leaf,
            vars: named ? ["provider": name!] : [:]
        )
    }

    /// The English of every localised failure sentence in the app, verbatim,
    /// under its full key.
    ///
    /// This is what the log and the "Copy error details" payload get, and what
    /// the UI falls back to if a key ever goes missing — all three stay English
    /// by decision (`docs/design-i18n.md` §"Which surfaces are targets").
    ///
    /// A table rather than literals at the call sites so the duplication is
    /// *checkable*: it is a second copy of the locale files, and a reworded
    /// sentence that landed in only one of them is failure class 3 with nothing
    /// to report it. `tests/test_pipeline_failure_keys.py` groups these by key
    /// prefix and asserts each group equals its `en` block, so the copy cannot
    /// drift silently — and a new prefix is enrolled by adding it there.
    static let englishSentences: [String: String] = [
        "desktop.pipeline.failure.stranded": "Analysis stopped unexpectedly.",
        "desktop.pipeline.failure.launchFailed": "Couldn't start the analysis. {{reason}}",
        "desktop.pipeline.failure.auth": "Your {{provider}} key was rejected.",
        "desktop.pipeline.failure.authGeneric": "Your API key was rejected.",
        "desktop.pipeline.failure.outOfCredit": "{{provider}} is out of credit.",
        "desktop.pipeline.failure.outOfCreditGeneric": "Your AI provider account is out of credit.",
        "desktop.pipeline.failure.network": "Couldn't reach {{provider}}. Check your connection.",
        "desktop.pipeline.failure.networkGeneric": "Couldn't reach the AI provider. Check your connection.",
        "desktop.pipeline.failure.quota": "{{provider}} rate limit reached. Try again soon.",
        "desktop.pipeline.failure.quotaGeneric": "Rate limit reached. Try again soon.",
        "desktop.pipeline.failure.apiRequest": "{{provider}} rejected the request.",
        "desktop.pipeline.failure.apiRequestGeneric": "The AI provider rejected the request.",
        "desktop.pipeline.failure.apiServer": "{{provider}} is unavailable. Try again shortly.",
        "desktop.pipeline.failure.apiServerGeneric": "The AI provider is unavailable. Try again shortly.",
        "desktop.pipeline.failure.outputTruncated": "This session is too dense for {{provider}}'s output limit. Try a model with a larger output, or split the recording.",
        "desktop.pipeline.failure.outputTruncatedGeneric": "This session is too dense for the model's output limit. Try a model with a larger output, or split the recording.",
        "desktop.pipeline.failure.disk": "Not enough disk space.",
        "desktop.pipeline.failure.whisper": "Transcription failed — the speech model didn't load.",
        "desktop.pipeline.failure.userSignal": "Run was stopped.",
        "desktop.pipeline.failure.missingDep": "Setup needed — a required tool isn't installed.",
        "desktop.pipeline.failure.missingInput": "A required input file is missing.",
        "desktop.pipeline.failure.missingBinary": "FFmpeg couldn't be found.",
        "desktop.pipeline.failure.outputExists": "Already analysed — re-analysing would replace the existing results.",
        "desktop.pipeline.failure.unusableInput": "Some files couldn't be analysed.",
        "desktop.pipeline.failure.unknown": "Something went wrong during analysis.",
        "desktop.llmSettings.revalidating": "Last validation was rejected — re-checking…",
        "desktop.llmSettings.validation.outOfCredit": "{{provider}} is out of credit. Your key is fine — top up your account to use it.",
        "desktop.llmSettings.validation.keyRejected": "{{provider}} rejected this key ({{status}}). It may have been deleted, rotated, or never had access — generate a new key in your provider dashboard.",
        "desktop.llmSettings.validation.rateLimited": "{{provider}} is rate-limited right now (429). Your key is fine — try again in a minute.",
        "desktop.llmSettings.validation.httpStatus": "{{provider}} returned HTTP {{status}}.",
        "desktop.llmSettings.validation.azureEndpointMissing": "Add the Azure endpoint URL to finish setting this up.",
        "desktop.llmSettings.validation.azureEndpointScheme": "The Azure endpoint must start with https:// — got “{{endpoint}}”.",
        "desktop.llmSettings.validation.azureNotFound": "Azure endpoint or deployment not found (404). The key is fine — check the endpoint URL and deployment name.",
        "desktop.llmSettings.validation.buildFailed": "Couldn’t build the request.",
        "desktop.llmSettings.validation.noResponse": "No response from {{provider}}.",
        "desktop.llmSettings.validation.timedOut": "Request timed out — {{provider}} didn’t respond in 5s.",
        "desktop.llmSettings.validation.offline": "No network connection. Your key was fine — we just can’t check it right now.",
        "desktop.llmSettings.validation.unreachable": "Couldn't reach {{provider}}. Check your connection.",
        "desktop.llmSettings.validation.networkError": "Network error reaching {{provider}}.",
        "desktop.llmSettings.validation.ollamaURLMissing": "Set the Ollama server URL.",
        "desktop.llmSettings.validation.ollamaURLInvalid": "The Ollama URL is not valid.",
        "desktop.llmSettings.validation.ollamaNoResponse": "No response from Ollama.",
        "desktop.llmSettings.validation.ollamaHTTPError": "Ollama returned HTTP {{status}}. Is the server running?",
        "desktop.llmSettings.validation.ollamaNoModels": "Ollama is reachable but has no models pulled. Run `ollama pull llama3.2:3b` to add one.",
        "desktop.llmSettings.validation.ollamaUnreachable": "Ollama isn’t reachable at {{url}}. Start it with `ollama serve` or open the Ollama app.",
        "desktop.llmSettings.validation.ollamaProbeFailed": "The Ollama check failed.",
    ]

    /// A message for any key in `englishSentences`, with its variables filled
    /// in. The one builder — `failure(for:provider:)` composes a key and comes
    /// through here too.
    ///
    /// Two pipeline keys have no `PipelineFailureCategory` because they describe
    /// a *moment* rather than a classified cause: `stranded` (the process died
    /// without writing a terminus) and `launchFailed` (the spawn threw). Both
    /// happen before there is a cause to classify.
    /// `tests/test_pipeline_failure_keys.py` lists them as `_MOMENT_KEYS`.
    static func keyed(_ key: String, vars: [String: String] = [:]) -> FailureMessage {
        FailureMessage(key: key, vars: vars, english: englishSentence(for: key, vars: vars))
    }

    /// `englishSentences[key]` with its variables filled in. Falls back to the
    /// key rather than trapping — a missing entry must not take out a failure
    /// report, which is the one moment the app is already in trouble.
    static func englishSentence(for key: String, vars: [String: String]) -> String {
        guard var value = englishSentences[key] else { return key }
        for (name, replacement) in vars {
            value = value.replacingOccurrences(of: "{{\(name)}}", with: replacement)
        }
        return value
    }
}
