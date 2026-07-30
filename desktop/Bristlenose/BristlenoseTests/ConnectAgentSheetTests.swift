import Testing

@testable import Bristlenose

/// The sheet's one real decision: the payload each client dialect gets.
/// Dialects rot (verified 30 Jul 2026 against the installed `claude` CLI and
/// learn.chatgpt.com) — these tests pin what we believe today so a dialect
/// update is a deliberate edit, not silent drift.
struct ConnectAgentSheetTests {

    private let endpoint = "http://127.0.0.1:8150/mcp/"
    private let token = "tok_abc123"

    @Test func everyDialectCarriesBothPrimitives() {
        for client in ConnectAgentSheet.Client.allCases {
            let payload = client.payload(endpoint: endpoint, token: token)
            #expect(payload.contains(endpoint))
            #expect(payload.contains("Bearer \(token)"))
        }
    }

    @Test func claudeDesktopIsTheFullMcpServersWrapper() {
        // A wrapper, not a fragment: the config file often has no
        // mcpServers key, so the payload must stand alone as a new
        // top-level key (QA walk, 31 Jul 2026).
        let payload = ConnectAgentSheet.Client.claudeDesktop
            .payload(endpoint: endpoint, token: token)
        #expect(payload.hasPrefix("\"mcpServers\": {"))
        #expect(payload.contains("\"bristlenose\": {"))
        #expect(payload.contains("\"url\": \"\(endpoint)\""))
        #expect(payload.contains("\"Authorization\": \"Bearer \(token)\""))
    }

    @Test func claudeCodeIsAnAddCommand() {
        let payload = ConnectAgentSheet.Client.claudeCode
            .payload(endpoint: endpoint, token: token)
        #expect(payload.hasPrefix("claude mcp add --transport http bristlenose"))
        #expect(payload.contains("--header \"Authorization: Bearer \(token)\""))
    }

    @Test func chatgptCodexIsATOMLTable() {
        let payload = ConnectAgentSheet.Client.chatgptCodex
            .payload(endpoint: endpoint, token: token)
        #expect(payload.contains("[mcp_servers.bristlenose]"))
        #expect(payload.contains("url = \"\(endpoint)\""))
        #expect(payload.contains("http_headers = { \"Authorization\" = \"Bearer \(token)\" }"))
    }
}
