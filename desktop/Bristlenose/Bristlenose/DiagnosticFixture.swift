import Foundation
import os

/// Debug-only injector that overrides a project's `PipelineState` with a
/// synthesized `PipelineSummary`. Lets a contributor reproduce
/// `.completedPartial` / `.failedWithDiagnostic` without provoking a real
/// run. Set `BRISTLENOSE_DEBUG_DIAGNOSTIC_FIXTURE=<scenario_name>` in the
/// active Xcode scheme; `PipelineActivityItem` reads it on first appear and
/// overrides `pipelineRunner.state[project.id]`. Gated by `#if DEBUG` so
/// the env-var read + the scenario tables are absent from Release builds.
///
/// **Scenarios are embedded as Swift code, not loaded from JSON.** Earlier
/// versions read `tests/fixtures/pipeline-summary-*.json` via `#filePath`
/// path-walk; App Sandbox blocks reads outside the bundle/container, so
/// the file-IO path silently no-op'd under sandbox-on Debug builds. Inline
/// Swift sidesteps the sandbox entirely and keeps the harness reliable.
///
/// Scenarios are intentionally a superset of the contract fixture's so a
/// contributor can also reproduce the wire-shape lock cases without
/// adding a separate path. If the contract grows a new scenario worth
/// eyeballing, mirror it here too.
enum DiagnosticFixture {

    static let envVar = "BRISTLENOSE_DEBUG_DIAGNOSTIC_FIXTURE"

    #if DEBUG
    private static let logger = Logger(
        subsystem: "app.bristlenose", category: "diagnostic-fixture"
    )
    #endif

    /// Result of loading a scenario. `.none` = env var unset / Release build.
    /// `.clean` = scenario has zero failures — caller should NOT override
    /// (matches the spec's "clean run keeps `.ready`" regression check).
    enum Result {
        case none
        case clean
        case partial(PipelineSummary)
        case failed(PipelineSummary)
    }

    #if DEBUG
    static func loadIfEnabled() -> Result {
        guard let name = ProcessInfo.processInfo.environment[envVar],
              !name.isEmpty else {
            logger.info("env var unset; harness not firing")
            return .none
        }
        logger.info("env var = \(name, privacy: .public)")

        guard let scenario = scenarios[name] else {
            logger.warning(
                "scenario '\(name, privacy: .public)' not found; valid names: \(scenarios.keys.sorted().joined(separator: ", "), privacy: .public)"
            )
            return .none
        }

        let summary = scenario.summary
        if summary.totalFailureCount == 0 {
            logger.info("clean scenario; no override")
            return .clean
        }
        logger.info(
            "injecting \(scenario.event.rawValue, privacy: .public); failures=\(summary.totalFailureCount, privacy: .public)"
        )
        switch scenario.event {
        case .runFailed:    return .failed(summary)
        case .runCompleted: return .partial(summary)
        }
    }
    #else
    static func loadIfEnabled() -> Result { .none }
    #endif

    // MARK: - Embedded scenario tables (Debug only)

    #if DEBUG
    private enum FixtureEvent: String {
        case runCompleted = "run_completed"
        case runFailed = "run_failed"
    }

    private struct FixtureScenario {
        let event: FixtureEvent
        let summary: PipelineSummary
    }

    /// Mirrors `tests/fixtures/pipeline-summary-contract.json` (the
    /// cross-language contract — keep aligned with the Python writer) plus
    /// rich showcase scenarios for visual evaluation. Add new scenarios at
    /// the bottom; do not renumber session_id values.
    private static let scenarios: [String: FixtureScenario] = [

        // MARK: Contract-mirrored scenarios

        "run_completed_partial": FixtureScenario(
            event: .runCompleted,
            summary: PipelineSummary(
                transcripts: StageOutcome(
                    attempted: 5, succeeded: 3, durationMs: 723_000,
                    failed: [
                        sessionFailure(
                            sid: "s2", category: .whisper,
                            message: "Whisper transcription timed out after 600s",
                            stage: "s05_transcribe"),
                        sessionFailure(
                            sid: "s5", category: .missingBinary,
                            message: "[Errno 2] No such file or directory: 'ffmpeg'",
                            stage: "s05_transcribe"),
                    ]),
                topics: StageOutcome(attempted: 3, succeeded: 3, durationMs: 41_000, failed: []),
                quotes: StageOutcome(attempted: 3, succeeded: 3, durationMs: 82_000, failed: []),
                themes: nil)
        ),

        "run_failed_abandoned": FixtureScenario(
            event: .runFailed,
            summary: PipelineSummary(
                transcripts: StageOutcome(attempted: 3, succeeded: 3, durationMs: 412_000, failed: []),
                topics: StageOutcome(attempted: 3, succeeded: 3, durationMs: 39_000, failed: []),
                quotes: StageOutcome(
                    attempted: 3, succeeded: 0, durationMs: 18_000,
                    failed: [
                        sessionFailure(
                            sid: "s1", category: .auth,
                            message: "Anthropic API authentication failed: invalid API key",
                            stage: "s09_quote_extraction", code: "401", provider: "anthropic"),
                        sessionFailure(
                            sid: "s2", category: .auth,
                            message: "Anthropic API authentication failed: invalid API key",
                            stage: "s09_quote_extraction", code: "401", provider: "anthropic"),
                        sessionFailure(
                            sid: "s3", category: .auth,
                            message: "Anthropic API authentication failed: invalid API key",
                            stage: "s09_quote_extraction", code: "401", provider: "anthropic"),
                    ]),
                themes: nil)
        ),

        "run_failed_abandoned_at_topics": FixtureScenario(
            event: .runFailed,
            summary: PipelineSummary(
                transcripts: StageOutcome(attempted: 2, succeeded: 2, durationMs: 318_000, failed: []),
                topics: StageOutcome(
                    attempted: 2, succeeded: 0, durationMs: 14_000,
                    failed: [
                        sessionFailure(
                            sid: "s1", category: .quota,
                            message: "Topic segmentation failed: APIStatusError on anthropic",
                            stage: "topic_segmentation", code: "429", provider: "anthropic"),
                        sessionFailure(
                            sid: "s2", category: .quota,
                            message: "Topic segmentation failed: APIStatusError on anthropic",
                            stage: "topic_segmentation", code: "429", provider: "anthropic"),
                    ]),
                quotes: nil,
                themes: nil)
        ),

        "run_completed_partial_truncated": FixtureScenario(
            event: .runCompleted,
            summary: PipelineSummary(
                transcripts: StageOutcome(
                    attempted: 18, succeeded: 4, durationMs: 1_842_000,
                    failed:
                        (1...10).map { i in
                            sessionFailure(
                                sid: "s\(i)", category: .whisper,
                                message: "Whisper transcription timed out",
                                stage: "s05_transcribe")
                        } + [overflowPlaceholder(count: 4)]
                ),
                topics: StageOutcome(attempted: 4, succeeded: 4, durationMs: 54_000, failed: []),
                quotes: StageOutcome(attempted: 4, succeeded: 4, durationMs: 96_000, failed: []),
                themes: nil)
        ),

        "run_completed_clean": FixtureScenario(
            event: .runCompleted,
            summary: PipelineSummary(
                transcripts: StageOutcome(attempted: 3, succeeded: 3, durationMs: 412_000, failed: []),
                topics: StageOutcome(attempted: 3, succeeded: 3, durationMs: 41_000, failed: []),
                quotes: StageOutcome(attempted: 3, succeeded: 3, durationMs: 82_000, failed: []),
                themes: StageOutcome(attempted: 1, succeeded: 1, durationMs: 14_000, failed: []))
        ),

        // MARK: Rich showcase scenarios (visual evaluation)

        "showcase_partial_dense": FixtureScenario(
            event: .runCompleted,
            summary: PipelineSummary(
                transcripts: StageOutcome(
                    attempted: 8, succeeded: 4, durationMs: 1_842_000,
                    failed: [
                        sessionFailure(
                            sid: "s2", category: .whisper,
                            message: "Whisper transcription timed out after 600s. The 47-minute interview file exceeds the timeout cap; consider splitting the recording or raising BRISTLENOSE_WHISPER_TIMEOUT.",
                            stage: "s05_transcribe"),
                        sessionFailure(
                            sid: "s4", category: .missingBinary,
                            message: "[Errno 2] No such file or directory: 'ffmpeg' — bundled binary not found at expected path Contents/Resources/bin/ffmpeg",
                            stage: "s05_transcribe"),
                        sessionFailure(
                            sid: "s5", category: .disk,
                            message: "No space left on device while writing transcript output. Only 47 MB free on /Users/cassio/Documents — needs at least 2 GB headroom.",
                            stage: "s05_transcribe", code: "ENOSPC"),
                        sessionFailure(
                            sid: "s7", category: .missingBinary,
                            message: "ffprobe binary not executable: permission denied at /Applications/Bristlenose.app/Contents/Resources/bin/ffprobe",
                            stage: "s05_transcribe"),
                    ]),
                topics: StageOutcome(
                    attempted: 4, succeeded: 2, durationMs: 87_000,
                    failed: [
                        sessionFailure(
                            sid: "s1", category: .quota,
                            message: "Topic segmentation failed: rate limit exceeded on anthropic (retry-after: 47s)",
                            stage: "topic_segmentation", code: "429", provider: "anthropic"),
                        sessionFailure(
                            sid: "s3", category: .quota,
                            message: "Topic segmentation failed: monthly quota exhausted (resets 2026-06-01)",
                            stage: "topic_segmentation", code: "429", provider: "anthropic"),
                    ]),
                quotes: StageOutcome(
                    attempted: 2, succeeded: 1, durationMs: 124_000,
                    failed: [
                        sessionFailure(
                            sid: "s6", category: .network,
                            message: "Connection reset by peer mid-stream: lost network mid-extraction at 73% of session",
                            stage: "s09_quote_extraction", provider: "anthropic"),
                    ]),
                themes: nil)
        ),

        "showcase_failed_auth_burst": FixtureScenario(
            event: .runFailed,
            summary: PipelineSummary(
                transcripts: StageOutcome(attempted: 3, succeeded: 3, durationMs: 412_000, failed: []),
                topics: StageOutcome(attempted: 3, succeeded: 3, durationMs: 39_000, failed: []),
                quotes: StageOutcome(
                    attempted: 5, succeeded: 0, durationMs: 18_000,
                    failed: (1...5).map { i in
                        sessionFailure(
                            sid: "s\(i)", category: .auth,
                            message: i == 1
                                ? "Anthropic API returned 401: 'invalid_request_error: Your authentication credentials are invalid.' — verify your API key in Settings > LLM"
                                : "Anthropic API returned 401: 'invalid_request_error: Your authentication credentials are invalid.'",
                            stage: "s09_quote_extraction",
                            code: "401", provider: "anthropic")
                    }),
                themes: nil)
        ),

        "showcase_failed_multi_category": FixtureScenario(
            event: .runFailed,
            summary: PipelineSummary(
                transcripts: StageOutcome(
                    attempted: 5, succeeded: 2, durationMs: 612_000,
                    failed: [
                        sessionFailure(
                            sid: "s1", category: .whisper,
                            message: "Whisper transcription timed out after 600s. Recording length exceeds default cap.",
                            stage: "s05_transcribe"),
                        sessionFailure(
                            sid: "s2", category: .whisper,
                            message: "ctranslate2 OOM during model load. Free RAM dropped below 1.5 GB threshold.",
                            stage: "s05_transcribe"),
                        sessionFailure(
                            sid: "s3", category: .missingBinary,
                            message: "ffprobe not found in PATH — required for video duration detection.",
                            stage: "s05_transcribe"),
                    ]),
                topics: StageOutcome(
                    attempted: 4, succeeded: 1, durationMs: 92_000,
                    failed: [
                        sessionFailure(
                            sid: "s1", category: .quota,
                            message: "Anthropic rate limit reached (retry-after: 30s). Topic segmentation requires ~3000 tokens per session.",
                            stage: "topic_segmentation", code: "429", provider: "anthropic"),
                        sessionFailure(
                            sid: "s2", category: .quota,
                            message: "Anthropic rate limit reached (retry-after: 45s).",
                            stage: "topic_segmentation", code: "429", provider: "anthropic"),
                        sessionFailure(
                            sid: "s4", category: .quota,
                            message: "Anthropic monthly token quota exhausted. Upgrade plan or wait until 2026-06-01.",
                            stage: "topic_segmentation", code: "429", provider: "anthropic"),
                    ]),
                quotes: StageOutcome(
                    attempted: 2, succeeded: 0, durationMs: 8_400,
                    failed: [
                        sessionFailure(
                            sid: "s1", category: .auth,
                            message: "Anthropic API key rotated mid-run; subsequent calls returned 401.",
                            stage: "s09_quote_extraction", code: "401", provider: "anthropic"),
                        sessionFailure(
                            sid: "s2", category: .network,
                            message: "Connection timeout to api.anthropic.com after 60s. Likely captive portal or DNS issue.",
                            stage: "s09_quote_extraction", provider: "anthropic"),
                    ]),
                themes: nil)
        ),

        "showcase_truncated_varied": FixtureScenario(
            event: .runCompleted,
            summary: PipelineSummary(
                transcripts: StageOutcome(
                    attempted: 18, succeeded: 4, durationMs: 1_842_000,
                    failed: [
                        sessionFailure(sid: "s1", category: .whisper,
                            message: "Whisper transcription timed out after 600s for a 52-minute file.",
                            stage: "s05_transcribe"),
                        sessionFailure(sid: "s2", category: .missingBinary,
                            message: "ffmpeg not executable: permission denied.",
                            stage: "s05_transcribe"),
                        sessionFailure(sid: "s3", category: .disk,
                            message: "No space left on device while writing transcript JSON.",
                            stage: "s05_transcribe", code: "ENOSPC"),
                        sessionFailure(sid: "s4", category: .whisper,
                            message: "ctranslate2 segfault during model decode (signal 11).",
                            stage: "s05_transcribe"),
                        sessionFailure(sid: "s5", category: .network,
                            message: "Download of whisper-large-v3 failed at 47% (connection reset).",
                            stage: "s05_transcribe"),
                        sessionFailure(sid: "s6", category: .whisper,
                            message: "Audio file unreadable: stream has 0 channels (likely corrupt header).",
                            stage: "s05_transcribe"),
                        sessionFailure(sid: "s7", category: .missingBinary,
                            message: "ffprobe missing — can't extract duration metadata.",
                            stage: "s05_transcribe"),
                        sessionFailure(sid: "s8", category: .whisper,
                            message: "mlx_whisper failed to load metallib at @rpath/mlx.metallib.",
                            stage: "s05_transcribe"),
                        sessionFailure(sid: "s9", category: .disk,
                            message: "Disk full at /tmp during ffmpeg intermediate WAV extraction.",
                            stage: "s05_transcribe", code: "ENOSPC"),
                        sessionFailure(sid: "s10", category: .whisper,
                            message: "Out of memory during beam-search decode.",
                            stage: "s05_transcribe"),
                        overflowPlaceholder(count: 4),
                    ]),
                topics: StageOutcome(attempted: 4, succeeded: 4, durationMs: 54_000, failed: []),
                quotes: StageOutcome(attempted: 4, succeeded: 4, durationMs: 96_000, failed: []),
                themes: nil)
        ),

        // Debug-only swatch: triggers a `.completedPartial` (so the pill
        // is visible) but PipelineActivityItem's popover body intercepts
        // this scenario name and renders the 5-glyph reference card
        // instead. Use this to eyeball the full MessageKind vocabulary
        // (symbol + tint pairs for every kind, alongside the CLI Unicode
        // glyph for comparison).
        "showcase_all_glyphs": FixtureScenario(
            event: .runCompleted,
            summary: PipelineSummary(
                transcripts: StageOutcome(
                    attempted: 1, succeeded: 0, durationMs: 0,
                    failed: [
                        sessionFailure(
                            sid: "x", category: .unknown,
                            message: "glyph swatch placeholder",
                            stage: "swatch")
                    ]),
                topics: nil, quotes: nil, themes: nil)
        ),

        // Realistic partial: the most common real-world shape. One bucket
        // (transcripts), 4 failures across 12 sessions, errors only — what
        // a typical researcher would see when ffmpeg/whisper hiccups hit a
        // study mid-batch. Messages are real-shaped (varied length,
        // varied detail) so you can judge the popover the way a real
        // researcher would experience it on a real bad-Monday morning.
        "showcase_typical_partial": FixtureScenario(
            event: .runCompleted,
            summary: PipelineSummary(
                transcripts: StageOutcome(
                    attempted: 12, succeeded: 8, durationMs: 2_847_000,
                    failed: [
                        sessionFailure(
                            sid: "s3", category: .whisper,
                            message: "Whisper transcription timed out after 600s",
                            stage: "s05_transcribe"),
                        sessionFailure(
                            sid: "s7", category: .missingBinary,
                            message: "ffprobe not found at /Applications/Bristlenose.app/Contents/Resources/bin/ffprobe — bundled binary may be missing or unreadable",
                            stage: "s05_transcribe"),
                        sessionFailure(
                            sid: "s9", category: .whisper,
                            message: "Audio file unreadable: stream has 0 channels (likely corrupt header from a partially-downloaded recording)",
                            stage: "s05_transcribe"),
                        sessionFailure(
                            sid: "s11", category: .disk,
                            message: "No space left on device",
                            stage: "s05_transcribe", code: "ENOSPC"),
                    ]),
                topics: StageOutcome(attempted: 8, succeeded: 8, durationMs: 187_000, failed: []),
                quotes: StageOutcome(attempted: 8, succeeded: 8, durationMs: 412_000, failed: []),
                themes: StageOutcome(attempted: 1, succeeded: 1, durationMs: 24_000, failed: []))
        ),

        // Debug-only design-review: real popover layout (real fonts,
        // real Grid columns, real spacing) with rows showing all 5
        // MessageKinds and message lengths from short to wrapping.
        // Production diagnostic popover only shows `.error` and `.warning`
        // — this scenario is for visual design assessment of the
        // typographic ladder, not a real-data path.
        "showcase_all_states": FixtureScenario(
            event: .runCompleted,
            summary: PipelineSummary(
                transcripts: StageOutcome(
                    attempted: 1, succeeded: 0, durationMs: 0,
                    failed: [
                        sessionFailure(
                            sid: "x", category: .unknown,
                            message: "all-states placeholder",
                            stage: "swatch")
                    ]),
                topics: nil, quotes: nil, themes: nil)
        ),

        "showcase_overflow_one": FixtureScenario(
            event: .runCompleted,
            summary: PipelineSummary(
                transcripts: StageOutcome(
                    attempted: 15, succeeded: 4, durationMs: 1_542_000,
                    failed: (1...10).map { i in
                        sessionFailure(
                            sid: "s\(i)", category: .whisper,
                            message: "Whisper transcription timed out.",
                            stage: "s05_transcribe")
                    } + [overflowPlaceholder(count: 1)]),
                topics: StageOutcome(attempted: 4, succeeded: 4, durationMs: 54_000, failed: []),
                quotes: StageOutcome(attempted: 4, succeeded: 4, durationMs: 96_000, failed: []),
                themes: nil)
        ),
    ]

    // MARK: - Constructors (terse helpers — keep the scenario tables readable)

    private static func sessionFailure(
        sid: String,
        category: CauseCategory,
        message: String,
        stage: String,
        code: String? = nil,
        provider: String? = nil
    ) -> SessionFailure {
        SessionFailure(
            sessionId: sid,
            cause: Cause(
                category: category, code: code, message: message,
                provider: provider, stage: stage, sessionId: sid,
                exitCode: nil, signal: nil, signalName: nil
            )
        )
    }

    private static func overflowPlaceholder(count: Int) -> SessionFailure {
        // Matches the wire shape Python's `_truncate_failed` emits.
        // `session_id == nil && message.hasPrefix("... and ")` is what
        // `SessionFailure.isOverflowPlaceholder` detects.
        SessionFailure(
            sessionId: nil,
            cause: Cause(
                category: .unknown,
                code: nil,
                message: count == 1
                    ? "... and 1 more failure truncated"
                    : "... and \(count) more failures truncated",
                provider: nil, stage: nil, sessionId: nil,
                exitCode: nil, signal: nil, signalName: nil
            )
        )
    }
    #endif
}
