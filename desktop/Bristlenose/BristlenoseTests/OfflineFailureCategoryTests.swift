import Testing
@testable import Bristlenose

/// c-offline — with the Wi-Fi off, the first Analyse stops at the run's setup check
/// before its lifecycle opens, so the category comes from the printed table alone.
/// The lines below are that table, captured from `bristlenose run` under
/// `tests/offline_guard.py` (every non-loopback name refused) on 26 Nov 2026. It read
/// as `.unknown` ("Something went wrong during analysis.") until `can't reach` joined
/// the network arm; `.network` shows "Couldn't reach Claude. Check your connection."
@MainActor
@Suite("Failure category: the setup check with the network off")
struct OfflineFailureCategoryTests {

    static let offlineTable = [
        "Checking your setup",
        " ✓ FFmpeg          8.1.1 (/opt/homebrew/bin/ffmpeg)",
        " ✓ FFprobe         /opt/homebrew/bin/ffprobe",
        " ✓ Transcription   mlx-whisper 0.4.3 (MLX)",
        " — Whisper model   large-v3-turbo not cached (~1.6 GB download on first run)",
        " ✓ API key         Anthropic (sk-ant-...000) (could not validate: [Errno 8] ",
        "nodename nor servname provided, or not known)",
        " ✗ Network         Can't reach api.anthropic.com",
        " — PII redaction   off (use --redact-pii to enable)",
        " ✓ Disk space      39 GB free",
        " ✓ Serve mode      6 deps installed",
        "",
        "Check your internet connection. If you're behind a proxy:",
        "  export HTTPS_PROXY=http://proxy:port",
    ]

    @Test("The offline setup check is a network failure, not an unknown one")
    func offlineIsNetwork() {
        #expect(PipelineRunner.categoriseFailure(
            lines: Self.offlineTable, exitStatus: 1, provider: .claude) == .network)
    }

    @Test("Every cloud provider's offline row reads as network",
          arguments: [
              " ✗ Network         Can't reach api.openai.com",
              " ✗ Network         Can't reach generativelanguage.googleapis.com",
              " ✗ Network         Can't reach contoso.openai.azure.com",
              " ✗ Network         Can’t reach api.anthropic.com",
          ])
    func everyProviderRow(line: String) {
        #expect(PipelineRunner.categoriseFailure(lines: [line], exitStatus: 1) == .network)
    }

    @Test("A healthy network row does not make another failure a network one")
    func reachableIsNotNetwork() {
        let lines = [
            " ✗ API key         No Anthropic API key",
            " ✓ Network         api.anthropic.com reachable (142ms)",
        ]
        #expect(PipelineRunner.categoriseFailure(lines: lines, exitStatus: 1)
                == .providerNotSetUp)
    }
}
