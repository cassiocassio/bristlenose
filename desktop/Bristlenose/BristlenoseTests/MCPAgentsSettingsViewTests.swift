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

    // MARK: - The no-serve placeholder

    @Test func placeholderCarriesBothStubsInEveryDialect() {
        for client in MCPAgentsSettingsView.AgentClient.allCases {
            guard let placeholder = client.placeholderPayload else { continue }
            #expect(placeholder.contains(MCPAgentsSettingsView.AgentClient.placeholderEndpoint))
            #expect(placeholder.contains(MCPAgentsSettingsView.AgentClient.placeholderToken))
        }
    }

    @Test func claudeDesktopHasNoPlaceholderEither() {
        // Its tab is the Install button in both states — serve or no serve.
        #expect(MCPAgentsSettingsView.AgentClient.claudeDesktop.placeholderPayload == nil)
    }

    @Test func placeholderIsTheSameHeightAsTheLiveBlock() {
        // The no-reflow guarantee, mechanically. Line breaks come from the
        // dialect templates, not from the values, so a future dialect edit
        // that changed only one of the two would fail here rather than
        // silently making the pane jump when a serve comes up.
        for client in MCPAgentsSettingsView.AgentClient.allCases {
            guard let live = client.payload(endpoint: endpoint, token: token),
                  let placeholder = client.placeholderPayload else { continue }
            #expect(placeholder.split(separator: "\n", omittingEmptySubsequences: false).count
                    == live.split(separator: "\n", omittingEmptySubsequences: false).count)
        }
    }

    @Test func placeholderNeverLeaksARealValue() {
        // Cheap belt-and-braces: the stubs are built through the same
        // `payload(endpoint:token:)` as the live block, so a wiring slip
        // that passed a live endpoint or token through would show up here.
        for client in MCPAgentsSettingsView.AgentClient.allCases {
            guard let placeholder = client.placeholderPayload else { continue }
            #expect(placeholder.contains(endpoint) == false)
            #expect(placeholder.contains(token) == false)
        }
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

    @Test func zeroSessionsIsAnAnswer_notAMissingOne() throws {
        // Caught on screen 19 Aug 2026: the context menu offered Turn On Agent
        // Access on a project reading `0` sessions and `+57 unanalysed`. Both
        // arms of the old test said yes to it — `sessionCount != nil` is true
        // for a readable DB holding nothing, and the run stamp came from a run
        // that FAILED. There was nothing behind the door.
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("AgentAccessPolicyTests-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }

        var p = Project(id: UUID(), name: "folder-of-horrors", path: dir.path)
        #expect(AgentAccessPolicy.canShare(p, sessionCount: 0) == false)

        // And a failed run does not rescue it: a known zero outranks the stamp,
        // which is only consulted when the count is genuinely unknown.
        p.lastPipelineRunAt = Date()
        #expect(AgentAccessPolicy.canShare(p, sessionCount: 0) == false,
                "a run that produced nothing is not an analysis")
        // The window the stamp exists for still works — count not yet read.
        #expect(AgentAccessPolicy.canShare(p, sessionCount: nil) == true)
    }
}
