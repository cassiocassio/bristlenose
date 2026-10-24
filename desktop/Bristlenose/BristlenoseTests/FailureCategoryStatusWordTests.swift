import Testing
@testable import Bristlenose

/// N120 — `categoriseFailure` reads a status out of a preflight line with a bare
/// substring match, so a model id whose digits happen to hold `401` or `429`
/// (a compact date: `…-20250401`, `…-20240429`) is read as a key or a quota
/// problem before the model-not-found arm is reached. The Python classifier
/// (`run_lifecycle.py`) wraps the same digits in `\b`.
@MainActor
@Suite("Failure category: ids that hold a status number")
struct FailureCategoryStatusWordTests {

    @Test("A retired model whose id holds 401 or 429 is still the model",
          arguments: [
              "✗ Claude doesn't offer the model claude-sonnet-20250401.",
              "✗ Claude doesn't offer the model claude-haiku-20240429.",
              "Error code: 404 - {'type': 'error', 'error': {'type': 'not_found_error', 'message': 'model: claude-3-haiku-20240401'}}",
          ])
    func aDatedIdIsNotAStatus(line: String) {
        withKnownIssue("N120: the 401 / 429 inside the id wins over the model-not-found arm") {
            #expect(PipelineRunner.categoriseFailure(lines: [line], exitStatus: 2)
                    == .modelUnavailable)
        }
    }

    @Test("A real 401 and a real 429 still read as auth and quota")
    func realStatusesStillMatch() {
        #expect(PipelineRunner.categoriseFailure(
            lines: ["Error code: 401 - {'error': 'invalid x-api-key'}"], exitStatus: 2) == .auth)
        #expect(PipelineRunner.categoriseFailure(
            lines: ["Error code: 429 - too many requests"], exitStatus: 2) == .quota)
    }
}
