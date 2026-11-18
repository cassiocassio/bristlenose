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
        guard display != .off, provider != .ollama else { return nil }
        guard let terminus, terminus.event == "run_completed",
              terminus.runId != priorRunId else { return nil }
        let tokens = (terminus.inputTokens ?? 0) + (terminus.outputTokens ?? 0)
        guard tokens > 0 else { return nil }
        if display == .cost, let usd = terminus.costUsdEstimate, usd.isFinite, usd >= 0 {
            return .costUSD(usd)
        }
        return .tokens(tokens)
    }

    /// The localised line. Numbers use the Mac's own formatters: tokens in
    /// compact form ("412K"), dollars in the locale's way of writing US dollars
    /// ("$1.24" in the US, "US$1.24" where "$" means another dollar).
    @MainActor
    func text(i18n: I18n, locale: Locale = .current) -> String {
        switch self {
        case .tokens(let count):
            let compact = count.formatted(.number.notation(.compactName).locale(locale))
            return i18n.t("desktop.chrome.runUsageTokens", ["tokens": compact])
        case .costUSD(let usd):
            let dollars = FloatingPointFormatStyle<Double>.Currency(code: "USD").locale(locale)
            if usd < 0.01 {
                return i18n.t("desktop.chrome.runUsageCostUnderCent",
                              ["amount": 0.01.formatted(dollars)])
            }
            return i18n.t("desktop.chrome.runUsageCost", ["amount": usd.formatted(dollars)])
        }
    }
}
