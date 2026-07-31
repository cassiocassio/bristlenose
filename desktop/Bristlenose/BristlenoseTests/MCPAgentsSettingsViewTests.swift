import Foundation
import Testing

@testable import Bristlenose

/// The pane's two real decisions: the payload each client dialect gets, and
/// when a project can be offered Agent Access at all.
///
/// Dialects rot (verified 30 Jul 2026 against the installed `claude` CLI
/// and learn.chatgpt.com) — these pins make a dialect update a deliberate
/// edit, not silent drift. Migrated from the retired ConnectAgentSheet's
/// tests; Claude Desktop deliberately has NO payload any more (its tab is
/// the Install button — the extension's handshake carries the address and
/// token, so there is nothing to copy).
struct MCPAgentsSettingsViewTests {

    private let endpoint = "http://127.0.0.1:8150/mcp/"
    private let token = "tok_abc123"

    @Test func everyPayloadCarryingDialectHasBothPrimitives() {
        for client in MCPAgentsSettingsView.AgentClient.allCases {
            guard let payload = client.payload(endpoint: endpoint, token: token) else { continue }
            #expect(payload.contains(endpoint))
            #expect(payload.contains("Bearer \(token)"))
        }
    }

    @Test func claudeDesktopHasNoPayload_theInstallButtonIsTheTab() {
        #expect(MCPAgentsSettingsView.AgentClient.claudeDesktop
            .payload(endpoint: endpoint, token: token) == nil)
    }

    @Test func claudeCodeIsAnAddCommand() {
        let payload = MCPAgentsSettingsView.AgentClient.claudeCode
            .payload(endpoint: endpoint, token: token)
        #expect(payload?.hasPrefix("claude mcp add --transport http bristlenose") == true)
        #expect(payload?.contains("--header \"Authorization: Bearer \(token)\"") == true)
    }

    @Test func chatgptCodexIsATOMLTable() {
        let payload = MCPAgentsSettingsView.AgentClient.chatgptCodex
            .payload(endpoint: endpoint, token: token)
        #expect(payload?.contains("[mcp_servers.bristlenose]") == true)
        #expect(payload?.contains("url = \"\(endpoint)\"") == true)
        #expect(payload?.contains(
            "http_headers = { \"Authorization\" = \"Bearer \(token)\" }") == true)
    }

    @Test func genericIsTheTwoRawPrimitives() {
        // The fallback that makes replacing hand-paste safe: two values any
        // MCP client accepts, no dialect to rot.
        let payload = MCPAgentsSettingsView.AgentClient.generic
            .payload(endpoint: endpoint, token: token)
        #expect(payload == "\(endpoint)\nAuthorization: Bearer \(token)")
    }
}

/// §3.6a's gating table, pinned: hide only on the two KNOWABLE conditions.
@MainActor
struct AgentAccessPolicyTests {

    private func project(analysedAt: Date? = nil) -> Project {
        Project(id: UUID(), name: "P", path: "/tmp/nonexistent-\(UUID().uuidString)",
                lastPipelineRunAt: analysedAt)
    }

    @Test func notLocatable_cannotShare() {
        // The path doesn't exist → availability is not ready.
        #expect(AgentAccessPolicy.canShare(project(analysedAt: Date()), sessionCount: 3) == false)
    }

    @Test func locatable_needsAnAnalysedSignal() throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("AgentAccessPolicyTests-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }
        let p = Project(id: UUID(), name: "P", path: dir.path)

        // Neither signal: a never-analysed folder has no quotes to read.
        #expect(AgentAccessPolicy.canShare(p, sessionCount: nil) == false)
        // Watcher read a session count (covers pre-lastPipelineRunAt projects).
        #expect(AgentAccessPolicy.canShare(p, sessionCount: 4) == true)
        // A run completed this install (covers the pre-watcher-tick window).
        var analysed = p
        analysed.lastPipelineRunAt = Date()
        #expect(AgentAccessPolicy.canShare(analysed, sessionCount: nil) == true)
    }
}
