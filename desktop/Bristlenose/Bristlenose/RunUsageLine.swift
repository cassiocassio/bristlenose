import Foundation

/// Settings ▸ Appearance ▸ Show analysis usage (docs/design-llm-usage.md).
///
/// What the row says for a few seconds as a successful run ends: its token
/// count, its estimated cost, or nothing. The point is a sense of the scale of
/// a typical run, not a budget: limits, totals and the real bill belong to the
/// provider's own console.
enum AnalysisUsageDisplay: String, CaseIterable {
    case tokens
    case cost
    case off

    static let defaultsKey = "analysisUsageDisplay"
    /// Tokens: real counts the provider returned, and no money claim unless
    /// the researcher asks for one (owner, 18 Nov 2026).
    static let defaultValue: AnalysisUsageDisplay = .tokens

    static var current: AnalysisUsageDisplay {
        UserDefaults.standard.string(forKey: defaultsKey).flatMap(Self.init(rawValue:))
            ?? defaultValue
    }
}

/// The line a successful run leaves on its row for `shownFor`, then silence.
///
/// Read from the run's own terminus (`run_completed`), which already carries
/// the run's token totals and list-price estimate (`bristlenose/cost.py`). One
/// run only: never a running total.
enum RunUsageLine: Equatable {
    /// Input plus output tokens.
    case tokens(Int)
    /// US dollars at the provider's list price. Dollars, because every
    /// provider bills API use in dollars (owner, 18 Nov 2026).
    case costUSD(Double)

    static let shownFor: Duration = .seconds(5)

    /// The line for a run that ended, or nil for silence.
    ///
    /// Silence when: the setting is off; the run was local (Ollama costs
    /// nothing, and some builds report no usage, so a count would mislead);
    /// the terminus is not this run's completion (a failure, a warning or a
    /// stop keeps its own line); or the run made no LLM call (served from
    /// cache). Asked for cost but no price is on record (an Azure deployment,
    /// an any-llm route): the token count, which is still true.
    static func resolve(
        terminus: EventLogReader.Event?,
        priorRunId: String?,
        provider: LLMProvider?,
        display: AnalysisUsageDisplay
    ) -> RunUsageLine? {
        // No provider on record: silent, as the credit check is, rather than
        // risk a count for a local run whose provider went unrecorded.
        guard display != .off, let provider, provider != .ollama else { return nil }
        guard let terminus, terminus.event == "run_completed",
              terminus.runId != priorRunId else { return nil }
        let tokens = (terminus.inputTokens ?? 0) + (terminus.outputTokens ?? 0)
        guard tokens > 0 else { return nil }
        // A zero or bad price is not a cost worth saying ("under $0.01" would
        // be wrong for it): the token count is.
        if display == .cost, let usd = terminus.costUsdEstimate, usd.isFinite, usd > 0 {
            return .costUSD(usd)
        }
        return .tokens(tokens)
    }

    /// The localised line, numbers written in the app's own language (the
    /// house convention, as `SidebarSubtitleText`'s dates are): tokens in
    /// compact form ("412K"), dollars the way that language writes US dollars
    /// ("$1.24" in English, "US$" or "USD" where "$" would read as another).
    @MainActor
    func text(i18n: I18n) -> String {
        let locale = Locale(identifier: i18n.locale)
        switch self {
        case .tokens(let count):
            return i18n.t("desktop.chrome.runUsageTokens",
                          ["tokens": Self.compactTokens(count, locale: locale)])
        case .costUSD(let usd):
            if usd < 0.01 {
                return i18n.t("desktop.chrome.runUsageCostUnderCent",
                              ["amount": Self.dollars(0.01, locale: locale)])
            }
            return i18n.t("desktop.chrome.runUsageCost",
                          ["amount": Self.dollars(usd, locale: locale)])
        }
    }

    /// "412K" in English; pure, so the formatting is testable without an `I18n`.
    static func compactTokens(_ count: Int, locale: Locale) -> String {
        count.formatted(.number.notation(.compactName).locale(locale))
    }

    /// US dollars, written the way *locale* writes them.
    static func dollars(_ usd: Double, locale: Locale) -> String {
        usd.formatted(FloatingPointFormatStyle<Double>.Currency(code: "USD").locale(locale))
    }
}
