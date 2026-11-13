import Foundation
import Testing
@testable import Bristlenose

/// Tests for BristlenoseShared.redactKeys — the key-shape redactor.
/// Uses pattern-valid FAKE keys (all-same-char, obviously not real) so the
/// test source is safe to commit and can't leak credentials if grepped.
@Suite("BristlenoseShared.redactKeys")
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
        let out = BristlenoseShared.redactKeys(in: Self.fakeAnthropic)
        #expect(out == "***REDACTED***")
        #expect(!out.contains("sk-ant-api03"))
    }

    @Test func masks_anthropic_sid_key() {
        let out = BristlenoseShared.redactKeys(in: Self.fakeAnthropicSid)
        #expect(out == "***REDACTED***")
    }

    @Test func masks_openai_project_key() {
        let out = BristlenoseShared.redactKeys(in: Self.fakeOpenAIProj)
        #expect(out == "***REDACTED***")
        #expect(!out.contains("sk-proj-"))
    }

    @Test func masks_openai_historical_key() {
        let out = BristlenoseShared.redactKeys(in: Self.fakeOpenAIHistorical)
        #expect(out == "***REDACTED***")
    }

    @Test func masks_google_aiza_key() {
        let out = BristlenoseShared.redactKeys(in: Self.fakeGoogle)
        #expect(out == "***REDACTED***")
        #expect(!out.contains("AIza"))
    }

    // MARK: - Positive: key embedded in a larger line

    @Test func masks_key_in_env_dump_line() {
        let line = "ENV DUMP: FOO=bar BRISTLENOSE_ANTHROPIC_API_KEY=\(Self.fakeAnthropic) BAZ=qux"
        let out = BristlenoseShared.redactKeys(in: line)
        #expect(out.contains("FOO=bar"))
        #expect(out.contains("BAZ=qux"))
        #expect(out.contains("***REDACTED***"))
        #expect(!out.contains("sk-ant-api03"))
    }

    @Test func masks_multiple_keys_on_one_line() {
        let line = "keys: \(Self.fakeAnthropic) and \(Self.fakeGoogle)"
        let out = BristlenoseShared.redactKeys(in: line)
        #expect(!out.contains("sk-ant"))
        #expect(!out.contains("AIza"))
        // Count of REDACTED tokens should be 2
        let occurrences = out.components(separatedBy: "***REDACTED***").count - 1
        #expect(occurrences == 2)
    }

    @Test func masks_key_in_traceback_like_context() {
        let line = #"  File "bristlenose/llm/client.py", line 232, in _analyze: anthropic.AuthenticationError: invalid x-api-key: \#(Self.fakeAnthropic)"#
        let out = BristlenoseShared.redactKeys(in: line)
        #expect(out.contains("anthropic.AuthenticationError"))
        #expect(out.contains("***REDACTED***"))
        #expect(!out.contains("sk-ant-api03"))
    }

    // MARK: - Negative: things that must NOT be masked

    @Test func preserves_too_short_key_shape() {
        let line = "prefix sk-ant-api03-shorty not-a-real-key"
        let out = BristlenoseShared.redactKeys(in: line)
        #expect(out == line)  // unchanged — didn't meet 90-char floor
    }

    @Test func preserves_uuid() {
        let line = "session=12345678-1234-1234-1234-123456789abc"
        let out = BristlenoseShared.redactKeys(in: line)
        #expect(out == line)
    }

    @Test func preserves_file_path_with_lookalike() {
        let line = "/Users/cassio/Code/sk-ant-lookalike/foo.txt"
        let out = BristlenoseShared.redactKeys(in: line)
        #expect(out == line)
    }

    @Test func preserves_short_demo_string() {
        let line = "see sk-demo or sk-fake for examples"
        let out = BristlenoseShared.redactKeys(in: line)
        #expect(out == line)
    }

    @Test func preserves_docs_url() {
        // Docs URLs often reference sk-ant-... conceptually but shouldn't
        // carry full key-shaped tokens. A URL with "sk-ant" followed by
        // non-key text is fine.
        let line = "see https://docs.anthropic.com/api for sk-ant-... examples"
        let out = BristlenoseShared.redactKeys(in: line)
        #expect(out == line)
    }

    @Test func preserves_empty_line() {
        let out = BristlenoseShared.redactKeys(in: "")
        #expect(out == "")
    }

    @Test func preserves_plain_log_line() {
        let line = "2026-04-20 00:42:13 INFO stage=s10_quote_clustering progress=12/45"
        let out = BristlenoseShared.redactKeys(in: line)
        #expect(out == line)
    }
}

/// Azure key shapes (12 Nov 2026, `docs/design-azure-connection.md` §12): the
/// 84-character key as a whole token, and the 32-hex key only after a key-ish
/// word. The negatives are the point: a GUID request id, a dashless GUID, a
/// SHA-1, a SHA-256 and an MD5 must survive. All keys here are generated fakes.
@Suite("BristlenoseShared.redactKeys, Azure shapes")
@MainActor
struct AzureRedactorTests {

    static let fake84 = String((String(repeating: "aB3xY9kQ", count: 11)).prefix(84))
    static let fakeHex32 = String(repeating: "deadbeef", count: 4)
    static let guidRequestId = "3d1fae88-0000-4000-8000-000000000000"
    static let dashlessGuid = "3d1fae8800004000800000000000abcd"  // 32 hex, no key word
    static let sha1 = "da39a3ee5e6b4b0d3255bfef95601890afd80709"  // 40 hex
    static let sha256 = String(repeating: "ab12cd34", count: 8)  // 64 hex
    static let masked = "***REDACTED***"

    // MARK: - Positive controls

    @Test func fixtures_have_the_lengths_they_claim() {
        #expect(Self.fake84.count == 84)
        #expect(Self.fakeHex32.count == 32)
        #expect(Self.sha1.count == 40)
        #expect(Self.sha256.count == 64)
    }

    @Test func masks_84_char_key_standing_alone() {
        #expect(BristlenoseShared.redactKeys(in: Self.fake84) == Self.masked)
    }

    @Test func masks_84_char_key_in_a_header_line() {
        let out = BristlenoseShared.redactKeys(in: "api-key: \(Self.fake84)")
        #expect(out == "api-key: \(Self.masked)")
    }

    @Test func masks_84_char_key_in_a_url_query() {
        let out = BristlenoseShared.redactKeys(
            in: "GET https://x.openai.azure.com/openai/deployments/d?api-version=2024-10-21&key=\(Self.fake84) 401")
        #expect(!out.contains(Self.fake84))
        #expect(out.hasSuffix("&key=\(Self.masked) 401"))
    }

    @Test func masks_hex32_in_a_header_line() {
        #expect(BristlenoseShared.redactKeys(in: "api-key: \(Self.fakeHex32)")
                == "api-key: \(Self.masked)")
        #expect(BristlenoseShared.redactKeys(in: "Ocp-Apim-Subscription-Key: \(Self.fakeHex32)")
                == "Ocp-Apim-Subscription-Key: \(Self.masked)")
    }

    @Test func masks_hex32_after_authorization_bearer() {
        let out = BristlenoseShared.redactKeys(in: "Authorization: Bearer \(Self.fakeHex32)")
        #expect(out == "Authorization: Bearer \(Self.masked)")
    }

    @Test func masks_hex32_in_a_url_query() {
        let out = BristlenoseShared.redactKeys(in: "https://h/openai?api-version=2024-10-21&api_key=\(Self.fakeHex32)&x=1")
        #expect(out == "https://h/openai?api-version=2024-10-21&api_key=\(Self.masked)&x=1")
    }

    @Test func masks_hex32_in_an_env_line_and_in_json() {
        #expect(BristlenoseShared.redactKeys(in: "AZURE_OPENAI_API_KEY=\(Self.fakeHex32)")
                == "AZURE_OPENAI_API_KEY=\(Self.masked)")
        #expect(BristlenoseShared.redactKeys(in: #"{"key": "\#(Self.fakeHex32)"}"#)
                == #"{"key": "\#(Self.masked)"}"#)
    }

    // MARK: - Negative controls

    @Test func keeps_guid_request_id() {
        for line in ["apim-request-id: \(Self.guidRequestId)",
                     "x-request-id=\(Self.guidRequestId)",
                     "token=\(Self.guidRequestId)",
                     "key: \(Self.guidRequestId)"] {
            #expect(BristlenoseShared.redactKeys(in: line) == line)
        }
    }

    @Test func keeps_uuid4_hex_and_md5_without_a_key_word() {
        for line in ["request \(Self.dashlessGuid) done",
                     Self.dashlessGuid,
                     "md5 of the file is \(Self.fakeHex32) in prose",
                     "etag: \(Self.fakeHex32)"] {
            #expect(BristlenoseShared.redactKeys(in: line) == line)
        }
    }

    @Test func keeps_git_sha1_and_sha256_even_after_a_key_word() {
        for line in ["commit \(Self.sha1)", "key=\(Self.sha1)", "api-key: \(Self.sha256)",
                     "sha256: \(Self.sha256)", "HEAD is \(Self.sha1) on main"] {
            #expect(BristlenoseShared.redactKeys(in: line) == line)
        }
    }

    @Test func keeps_other_lengths_and_non_tokens_around_84() {
        let eightyThree = String(Self.fake84.dropLast())
        let eightyFive = Self.fake84 + "Z"
        let letters84 = String(repeating: "a", count: 84)
        let digits84 = String(repeating: "7", count: 84)
        for line in [eightyThree, eightyFive, letters84, digits84,
                     "/Users/x/\(Self.fake84)/file", "host.\(Self.fake84).example"] {
            #expect(BristlenoseShared.redactKeys(in: line) == line)
        }
    }
}

/// Tests for ServeManager.displayableLine — what of a sidecar stdout line is
/// kept in `outputLines` (shown selectable in the boot-failure pane, tail
/// quoted in exit errors). The bearer-token line is consumed, never kept:
/// `redactKeys` matches provider key shapes, not the bearer.
@Suite("ServeManager.displayableLine")
@MainActor
struct DisplayableLineTests {

    // Shape of secrets.token_urlsafe(32); obviously fake.
    static let fakeBearer = String(repeating: "Q", count: 43)

    @Test func drops_auth_token_line() {
        let line = ServeManager.authTokenLinePrefix + Self.fakeBearer
        #expect(ServeManager.displayableLine(line) == nil)
    }

    @Test func prefix_matches_the_python_print() {
        // bristlenose/server/app.py prints exactly this prefix.
        #expect(ServeManager.authTokenLinePrefix == "[bristlenose] auth-token: ")
    }

    @Test func keeps_ordinary_lines() {
        let line = "  Report: http://127.0.0.1:54321/report/"
        #expect(ServeManager.displayableLine(line) == line)
    }

    @Test func still_redacts_keys_on_kept_lines() {
        let line = "boom: " + HandleLineRedactorTests.fakeAnthropic
        let out = ServeManager.displayableLine(line)
        #expect(out == "boom: ***REDACTED***")
    }
}
