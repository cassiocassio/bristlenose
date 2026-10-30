import Testing
@testable import Bristlenose

/// N136 / N137 — the preflight's own refusal sentences for a rate-limited and an
/// empty account, read by `categoriseFailure` when a run stops before it starts
/// (the setup check prints them and exits, so no events-log cause carries them).
/// The strings are the ones `recovery_message` renders from
/// `bristlenose/locales/en/preflight.json` (`preflight.api_key.rate_limit`,
/// `no_credit`, `anyllm_rate_limit`, `anyllm_no_credit`), English on every channel,
/// one printed line per array element.
///
/// "rate-limiting" has no `rate limit` in it and "no API credit" no `credit
/// balance`, so before this the first fell to `.unknown` and the second was
/// read as out of credit only by luck: Claude's and ChatGPT's top-up note says
/// "credit balance" a few lines later.
@MainActor
@Suite("Failure category: the preflight's rate-limit and no-credit sentences")
struct FailureCategoryPreflightSentenceTests {

    private static let rateLimit =
        " is rate-limiting this account. Wait a minute and re-run, or reduce "
        + "`llm_concurrency` in your bristlenose.toml."

    @Test("Every provider's rate-limit refusal is a quota",
          arguments: [
              ("Claude", LLMProvider.claude),
              ("ChatGPT", .chatGPT),
              ("Azure OpenAI", .azure),
              ("Gemini", .gemini),
          ])
    func rateLimitRefusalIsQuota(name: String, provider: LLMProvider) {
        let lines = [name + Self.rateLimit]
        #expect(PipelineRunner.categoriseFailure(
            lines: lines, exitStatus: 2, provider: provider) == .quota)
    }

    @Test("A rate-limit refusal read with no provider chosen is still a quota")
    func rateLimitRefusalWithoutAProvider() {
        #expect(PipelineRunner.categoriseFailure(
            lines: ["Claude" + Self.rateLimit], exitStatus: 2) == .quota)
        // The any-llm sentence; its "Provider says:" line must not claim it first.
        #expect(PipelineRunner.categoriseFailure(
            lines: ["Mistral is rate-limiting this key. Wait a minute and re-run.",
                    "Provider says: Rate limit exceeded"], exitStatus: 2) == .quota)
    }

    @Test("Claude's and ChatGPT's no-credit refusal is out of credit, whole or by its first line",
          arguments: [
              (LLMProvider.claude,
               ["Your Claude account has no API credit available.",
                "Top up at https://console.anthropic.com/settings/billing",
                "($5 minimum credit purchase. A separate Claude.ai Pro/Max subscription does NOT fund API usage — the API has its own credit balance, refilled at Settings → Billing.)",
                "and re-run."]),
              (.chatGPT,
               ["Your ChatGPT account has no API credit available.",
                "Top up at https://platform.openai.com/account/billing",
                "($5 minimum credit purchase. A ChatGPT Plus/Pro subscription does NOT fund API usage — the API has its own credit balance, refilled at Billing → Add to credit balance.)",
                "and re-run."]),
              // The sentence on its own: the top-up note is separate wording and
              // must not be what the answer hangs on.
              (.claude, ["Your Claude account has no API credit available."]),
              (.chatGPT, ["Your ChatGPT account has no API credit available."]),
          ])
    func noCreditRefusalIsOutOfCredit(provider: LLMProvider, lines: [String]) {
        #expect(PipelineRunner.categoriseFailure(
            lines: lines, exitStatus: 2, provider: provider) == .outOfCredit)
    }

    @Test("The no-credit sentence is out of credit with no provider recorded, as on a first Claude key")
    func noCreditRefusalWithoutAProvider() {
        // `activeProvider` is nil until a gesture writes it.
        for lines in [
            ["Your Claude account has no API credit available."],
            ["Your ChatGPT account has no API credit available.",
             "Top up at https://platform.openai.com/account/billing"],
            ["Your Mistral account has no API credit available.",
             "Provider says: insufficient funds",
             "Top up in your Mistral account and re-run."],
        ] {
            #expect(PipelineRunner.categoriseFailure(lines: lines, exitStatus: 2) == .outOfCredit)
        }
    }

    @Test("A rate-limit sentence wrapped at 80 columns, as Rich prints it, is still a quota")
    func wrappedRateLimitRefusal() {
        #expect(PipelineRunner.categoriseFailure(
            lines: ["✗ Claude is rate-limiting this account. Wait a minute and re-run, or reduce",
                    "`llm_concurrency` in your bristlenose.toml."],
            exitStatus: 2, provider: .claude) == .quota)
    }

    @Test("The neighbours stay where they were",
          arguments: [
              ("Error code: 429 - Rate limit reached for gpt-4o", PipelineFailureCategory.quota),
              ("anthropic.RateLimitError: (429)", .quota),
              ("Error code: 401 - {'error': 'invalid x-api-key'}", .auth),
              ("Your Claude API key was rejected (HTTP 401).", .auth),
              ("✗ Claude doesn't offer the model claude-sonnet-20250401.", .modelUnavailable),
              ("Error code: 404 - {'type': 'error', 'error': {'type': 'not_found_error', 'message': 'model: claude-3-haiku-20240401'}}", .modelUnavailable),
              ("Provider says: something odd.", .apiRequest),
              ("Something else went wrong", .unknown),
          ])
    func neighboursHold(line: String, expected: PipelineFailureCategory) {
        #expect(PipelineRunner.categoriseFailure(
            lines: [line], exitStatus: 2, provider: .claude) == expected)
    }

    /// A Mac whose MLX is installed but cannot start (the Metal device will not create):
    /// the setup check names it ("mlx-whisper is installed but MLX cannot start on this
    /// Mac") and exits before the run begins. Before this it fell to `.unknown`, which
    /// reads "stopped unexpectedly" for a cause the researcher can act on.
    @Test("MLX that cannot start is a speech-model failure, not an unknown")
    func mlxThatCannotStartIsWhisper() {
        let lines = [
            " ✗ Transcription   mlx-whisper is installed but MLX cannot start on this Mac "
                + "(the probe was stopped by signal 5)",
        ]
        #expect(PipelineRunner.categoriseFailure(lines: lines, exitStatus: 1) == .whisper)
    }
}
