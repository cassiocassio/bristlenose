import Foundation
import Testing
@testable import Bristlenose

/// Tests for ServeManager.redactKeys — the key-shape redactor.
/// Uses pattern-valid FAKE keys (all-same-char, obviously not real) so the
/// test source is safe to commit and can't leak credentials if grepped.
@Suite("ServeManager.redactKeys")
@MainActor
struct HandleLineRedactorTests {

    // Pattern-valid fakes — never real keys.
    static let fakeAnthropic = "sk-ant-api03-" + String(repeating: "A", count: 95)
    static let fakeAnthropicSid = "sk-ant-sid12-" + String(repeating: "X", count: 92)
    static let fakeOpenAIProj = "sk-proj-" + String(repeating: "B", count: 48)
    static let fakeOpenAIHistorical = "sk-" + String(repeating: "C", count: 48)
    static let fakeGoogle = "AIza" + String(repeating: "D", count: 35)

    // MARK: - Positive: full key on a line

    @Test func masks_anthropic_api_key() {
        let out = ServeManager.redactKeys(in: Self.fakeAnthropic)
        #expect(out == "***REDACTED***")
        #expect(!out.contains("sk-ant-api03"))
    }

    @Test func masks_anthropic_sid_key() {
        let out = ServeManager.redactKeys(in: Self.fakeAnthropicSid)
        #expect(out == "***REDACTED***")
    }

    @Test func masks_openai_project_key() {
        let out = ServeManager.redactKeys(in: Self.fakeOpenAIProj)
        #expect(out == "***REDACTED***")
        #expect(!out.contains("sk-proj-"))
    }

    @Test func masks_openai_historical_key() {
        let out = ServeManager.redactKeys(in: Self.fakeOpenAIHistorical)
        #expect(out == "***REDACTED***")
    }

    @Test func masks_google_aiza_key() {
        let out = ServeManager.redactKeys(in: Self.fakeGoogle)
        #expect(out == "***REDACTED***")
        #expect(!out.contains("AIza"))
    }

    // MARK: - Positive: key embedded in a larger line

    @Test func masks_key_in_env_dump_line() {
        let line = "ENV DUMP: FOO=bar BRISTLENOSE_ANTHROPIC_API_KEY=\(Self.fakeAnthropic) BAZ=qux"
        let out = ServeManager.redactKeys(in: line)
        #expect(out.contains("FOO=bar"))
        #expect(out.contains("BAZ=qux"))
        #expect(out.contains("***REDACTED***"))
        #expect(!out.contains("sk-ant-api03"))
    }

    @Test func masks_multiple_keys_on_one_line() {
        let line = "keys: \(Self.fakeAnthropic) and \(Self.fakeGoogle)"
        let out = ServeManager.redactKeys(in: line)
        #expect(!out.contains("sk-ant"))
        #expect(!out.contains("AIza"))
        // Count of REDACTED tokens should be 2
        let occurrences = out.components(separatedBy: "***REDACTED***").count - 1
        #expect(occurrences == 2)
    }

    @Test func masks_key_in_traceback_like_context() {
        let line = #"  File "bristlenose/llm/client.py", line 232, in _analyze: anthropic.AuthenticationError: invalid x-api-key: \#(Self.fakeAnthropic)"#
        let out = ServeManager.redactKeys(in: line)
        #expect(out.contains("anthropic.AuthenticationError"))
        #expect(out.contains("***REDACTED***"))
        #expect(!out.contains("sk-ant-api03"))
    }

    // MARK: - Negative: things that must NOT be masked

    @Test func preserves_too_short_key_shape() {
        let line = "prefix sk-ant-api03-shorty not-a-real-key"
        let out = ServeManager.redactKeys(in: line)
        #expect(out == line)  // unchanged — didn't meet 90-char floor
    }

    @Test func preserves_uuid() {
        let line = "session=12345678-1234-1234-1234-123456789abc"
        let out = ServeManager.redactKeys(in: line)
        #expect(out == line)
    }

    @Test func preserves_file_path_with_lookalike() {
        let line = "/Users/cassio/Code/sk-ant-lookalike/foo.txt"
        let out = ServeManager.redactKeys(in: line)
        #expect(out == line)
    }

    @Test func preserves_short_demo_string() {
        let line = "see sk-demo or sk-fake for examples"
        let out = ServeManager.redactKeys(in: line)
        #expect(out == line)
    }

    @Test func preserves_docs_url() {
        // Docs URLs often reference sk-ant-... conceptually but shouldn't
        // carry full key-shaped tokens. A URL with "sk-ant" followed by
        // non-key text is fine.
        let line = "see https://docs.anthropic.com/api for sk-ant-... examples"
        let out = ServeManager.redactKeys(in: line)
        #expect(out == line)
    }

    @Test func preserves_empty_line() {
        let out = ServeManager.redactKeys(in: "")
        #expect(out == "")
    }

    @Test func preserves_plain_log_line() {
        let line = "2026-04-20 00:42:13 INFO stage=s10_quote_clustering progress=12/45"
        let out = ServeManager.redactKeys(in: line)
        #expect(out == line)
    }
}
