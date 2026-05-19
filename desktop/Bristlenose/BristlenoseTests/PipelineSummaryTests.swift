import Foundation
import Testing
@testable import Bristlenose

/// Tests for `PipelineSummary` Codable mirror + `dominantCategory()` +
/// `PipelineActivityItem.formatDiagnosticPlaintext`.
///
/// The Codable round-trip runs every scenario in
/// `tests/fixtures/pipeline-summary-contract.json` — both sides of the
/// cross-language contract must agree forever. Re-encoding produces a
/// `summary` payload that is key-equivalent to the input scenario's
/// `summary` (whitespace and field order may differ; field-by-field
/// equality on the decoded model is the truth).
struct PipelineSummaryTests {

    // MARK: - Fixture loader

    /// Walk up from this file to `tests/fixtures/pipeline-summary-contract.json`.
    private func fixturesURL() -> URL {
        // <worktree>/desktop/Bristlenose/BristlenoseTests/PipelineSummaryTests.swift
        // → <worktree>/tests/fixtures/pipeline-summary-contract.json
        let here = URL(fileURLWithPath: #filePath)
        let worktree = here
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        return worktree
            .appendingPathComponent("tests/fixtures/pipeline-summary-contract.json")
    }

    private func loadScenarios() throws -> [String: [String: Any]] {
        let url = fixturesURL()
        let data = try Data(contentsOf: url)
        guard let json = try JSONSerialization.jsonObject(with: data)
                as? [String: Any],
              let scenarios = json["scenarios"] as? [String: [String: Any]]
        else {
            Issue.record("Could not load contract fixture at \(url.path)")
            return [:]
        }
        return scenarios
    }

    private func summaryData(from scenario: [String: Any]) throws -> Data? {
        guard let summary = scenario["summary"] else { return nil }
        return try JSONSerialization.data(withJSONObject: summary)
    }

    // MARK: - Round-trip

    @Test func roundTripAllFixtureScenarios() throws {
        let scenarios = try loadScenarios()
        #expect(!scenarios.isEmpty, "fixture has at least one scenario")

        for (name, scenario) in scenarios {
            guard let data = try summaryData(from: scenario) else {
                // Some scenarios may have a null summary in the future;
                // skip explicitly so a null doesn't fail the test.
                continue
            }
            let decoded: PipelineSummary
            do {
                decoded = try JSONDecoder().decode(PipelineSummary.self, from: data)
            } catch {
                Issue.record("decode failed for scenario \(name): \(error)")
                continue
            }
            let reEncoded = try JSONEncoder().encode(decoded)
            let redecoded = try JSONDecoder().decode(
                PipelineSummary.self, from: reEncoded)
            #expect(decoded == redecoded, "round-trip mismatch for \(name)")
        }
    }

    // MARK: - dominantCategory precedence

    @Test func dominantCategoryEmptyIsUnknown() {
        let summary = PipelineSummary()
        #expect(summary.dominantCategory() == .unknown)
    }

    @Test func dominantCategoryHighestCountWins() {
        // 3 network, 1 auth → network wins on count alone (despite auth
        // being higher in the precedence chain — count matters first).
        let summary = makeSummary(failures: [
            (.network, 3), (.auth, 1),
        ])
        #expect(summary.dominantCategory() == .network)
    }

    @Test func dominantCategoryTieBreakAuthBeatsMissingBinary() {
        let summary = makeSummary(failures: [(.auth, 2), (.missingBinary, 2)])
        #expect(summary.dominantCategory() == .auth)
    }

    @Test func dominantCategoryTieBreakMissingBinaryBeatsQuota() {
        let summary = makeSummary(failures: [(.missingBinary, 2), (.quota, 2)])
        #expect(summary.dominantCategory() == .missingBinary)
    }

    @Test func dominantCategoryTieBreakQuotaBeatsNetwork() {
        let summary = makeSummary(failures: [(.quota, 2), (.network, 2)])
        #expect(summary.dominantCategory() == .quota)
    }

    @Test func dominantCategoryTieBreakNetworkBeatsUnknown() {
        let summary = makeSummary(failures: [(.network, 2), (.unknown, 2)])
        #expect(summary.dominantCategory() == .network)
    }

    @Test func dominantCategoryOffChainCollapsesToUnknown() {
        // `whisper` is a real category but not on the pill chain. A single
        // whisper failure should map to `.unknown` for the pill.
        let summary = makeSummary(failures: [(.whisper, 1)])
        #expect(summary.dominantCategory() == .unknown)
    }

    // MARK: - Fixture-derived state mapping

    @Test func fixtureRunCompletedPartialDominantIsMissingBinary() throws {
        // The partial scenario has 1 whisper + 1 missing_binary failure.
        // Counts tied at 1 each → precedence chain: missing_binary wins
        // (whisper is off-chain → unknown; missing_binary on-chain).
        let scenario = try requireScenario("run_completed_partial")
        let summary = try decodeSummary(from: scenario)
        #expect(summary.totalFailureCount == 2)
        #expect(summary.dominantCategory() == .missingBinary)
    }

    @Test func fixtureRunFailedAbandonedDominantIsAuth() throws {
        let scenario = try requireScenario("run_failed_abandoned")
        let summary = try decodeSummary(from: scenario)
        #expect(summary.dominantCategory() == .auth)
    }

    @Test func fixtureRunFailedAbandonedAtTopicsDominantIsQuota() throws {
        // Verifies stage-resolution looks at the topics bucket, not just quotes.
        let scenario = try requireScenario("run_failed_abandoned_at_topics")
        let summary = try decodeSummary(from: scenario)
        #expect(summary.dominantCategory() == .quota)
        #expect(summary.topics?.failed.count == 2)
        #expect(summary.quotes == nil)
    }

    @Test func fixtureTruncatedOverflowPlaceholderDetected() throws {
        let scenario = try requireScenario("run_completed_partial_truncated")
        let summary = try decodeSummary(from: scenario)
        let transcripts = try #require(summary.transcripts)
        // 10 real failures + 1 overflow placeholder.
        #expect(transcripts.failed.count == 11)
        let overflow = transcripts.failed.last
        #expect(overflow?.isOverflowPlaceholder == true)
        let realFailures = transcripts.failed.filter { !$0.isOverflowPlaceholder }
        #expect(realFailures.count == 10)
    }

    @Test func fixtureRunCompletedCleanHasZeroFailures() throws {
        // Regression: a clean run with a populated summary must NOT trigger
        // `.completedPartial` in the EventLogReader — totalFailureCount=0
        // is the gate.
        let scenario = try requireScenario("run_completed_clean")
        let summary = try decodeSummary(from: scenario)
        #expect(summary.totalFailureCount == 0)
    }

    // MARK: - Plaintext formatter

    @Test func plaintextIncludesDominantCategoryAndBucketHeaders() throws {
        let scenario = try requireScenario("run_completed_partial")
        let summary = try decodeSummary(from: scenario)
        let text = PipelineActivityItem.formatDiagnosticPlaintext(
            summary: summary,
            projectName: "Test Project",
            projectPath: "/Users/x/path",
            abandoned: false
        )
        #expect(text.contains("Project: Test Project"))
        #expect(text.contains("Outcome: Partial completion"))
        #expect(text.contains("Dominant category: missing_binary"))
        #expect(text.contains("Stage: transcripts"))
        // No themes failures in this scenario — header should not appear.
        #expect(!text.contains("Stage: themes"))
    }

    @Test func plaintextOverflowMarkerUsesWarningGlyph() throws {
        let scenario = try requireScenario("run_completed_partial_truncated")
        let summary = try decodeSummary(from: scenario)
        let text = PipelineActivityItem.formatDiagnosticPlaintext(
            summary: summary,
            projectName: "X", projectPath: "/p",
            abandoned: false
        )
        #expect(text.contains("⚠ ... and 4 more failures truncated"))
        // And the 10 real failures use the error glyph.
        #expect(text.contains("✗ s1  whisper"))
    }

    // MARK: - Localised overflow text (Finding 40)

    /// Path to the worktree's production `bristlenose/locales/` directory.
    /// We use the real locale files (not the BristlenoseTests fixtures),
    /// because the keys under test (`overflow_one` / `overflow_other`) only
    /// exist in production locales.
    private static let productionLocalesURL: URL = {
        // <worktree>/desktop/Bristlenose/BristlenoseTests/PipelineSummaryTests.swift
        // → <worktree>/bristlenose/locales/
        let here = URL(fileURLWithPath: #filePath)
        let worktree = here
            .deletingLastPathComponent()  // BristlenoseTests/
            .deletingLastPathComponent()  // Bristlenose/ (Xcode project)
            .deletingLastPathComponent()  // desktop/
            .deletingLastPathComponent()  // <worktree>
        return worktree.appendingPathComponent("bristlenose/locales")
    }()

    @MainActor @Test func localisedOverflowText_singularPluralBranch() {
        // count=1 should dispatch to `overflow_one` and render the singular
        // form ("1 more failure truncated"). A wrong plural key here would
        // render silently as the raw key string — exactly the kind of
        // regression a user-visible-but-not-asserted bug hides.
        let i18n = I18n()
        i18n.configure(localesDirectory: Self.productionLocalesURL)
        let rendered = PipelineActivityItem.localisedOverflowText(
            message: "... and 1 more failure truncated", i18n: i18n
        )
        // English singular form contains "1 more failure" (singular). The
        // exact string is owned by the locale file; we assert the
        // structural invariant rather than the exact wording.
        #expect(rendered.contains("1"))
        #expect(rendered.contains("more failure"))
        // Negative: should not render the raw key.
        #expect(!rendered.contains("overflow_one"))
        // Negative: should not contain the plural form.
        #expect(!rendered.contains("failures"))
    }

    @MainActor @Test func localisedOverflowText_pluralBranch() {
        // count=N (N > 1) dispatches to `overflow_other`.
        let i18n = I18n()
        i18n.configure(localesDirectory: Self.productionLocalesURL)
        let rendered = PipelineActivityItem.localisedOverflowText(
            message: "... and 4 more failures truncated", i18n: i18n
        )
        #expect(rendered.contains("4"))
        #expect(rendered.contains("failures"))
        #expect(!rendered.contains("overflow_other"))
    }

    @MainActor @Test func localisedOverflowText_fallsBackToRawWhenRegexFails() {
        // When the wire message doesn't match the regex (count un-extractable),
        // the function should fall back to the raw message — not render the
        // locale key as a literal.
        let i18n = I18n()
        i18n.configure(localesDirectory: Self.productionLocalesURL)
        let rendered = PipelineActivityItem.localisedOverflowText(
            message: "no count here", i18n: i18n
        )
        #expect(rendered == "no count here")
    }

    // MARK: - Overflow count parser (Finding 3)

    @Test func parseOverflowCountMatchesPythonWireString() {
        // Exact shape Python emits — `bristlenose/events.py::_truncate_failed`.
        let cases: [(String, Int?)] = [
            ("... and 4 more failures truncated", 4),
            ("... and 1 more failure truncated", 1),
            ("… and 42 more failures truncated", 42),  // unicode ellipsis
            ("Whisper timed out", nil),                  // unrelated message
            ("and lots more truncated", nil),            // no digits
            ("", nil),
        ]
        for (input, expected) in cases {
            #expect(
                PipelineActivityItem.parseOverflowCount(from: input) == expected,
                "input: \(input)"
            )
        }
    }

    @Test func plaintextSanitisesProjectPath() throws {
        let scenario = try requireScenario("run_failed_abandoned")
        let summary = try decodeSummary(from: scenario)
        let text = PipelineActivityItem.formatDiagnosticPlaintext(
            summary: summary,
            projectName: "X",
            projectPath: "/Users/someone/secret/path",
            abandoned: true
        )
        #expect(!text.contains("/Users/someone/secret/path"))
    }

    // MARK: - Helpers

    private func requireScenario(_ name: String) throws -> [String: Any] {
        let scenarios = try loadScenarios()
        guard let scenario = scenarios[name] else {
            Issue.record("fixture missing scenario \(name)")
            return [:]
        }
        return scenario
    }

    private func decodeSummary(from scenario: [String: Any]) throws -> PipelineSummary {
        guard let data = try summaryData(from: scenario) else {
            Issue.record("scenario has no summary")
            return PipelineSummary()
        }
        return try JSONDecoder().decode(PipelineSummary.self, from: data)
    }

    /// Build a summary that pushes the given failures into the `quotes`
    /// bucket (arbitrary choice — `dominantCategory` is bucket-agnostic).
    private func makeSummary(
        failures: [(category: CauseCategory, count: Int)]
    ) -> PipelineSummary {
        let sessionFailures: [SessionFailure] = failures.flatMap { entry -> [SessionFailure] in
            (0..<entry.count).map { i in
                SessionFailure(
                    sessionId: "s\(i)-\(entry.category.rawValue)",
                    cause: Cause(
                        category: entry.category,
                        code: nil, message: nil, provider: nil,
                        stage: nil, sessionId: nil,
                        exitCode: nil, signal: nil, signalName: nil
                    )
                )
            }
        }
        let outcome = StageOutcome(
            attempted: sessionFailures.count,
            succeeded: 0,
            durationMs: 0,
            failed: sessionFailures
        )
        return PipelineSummary(
            transcripts: nil, topics: nil, quotes: outcome, themes: nil
        )
    }
}
