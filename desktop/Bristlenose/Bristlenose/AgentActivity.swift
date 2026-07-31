import Foundation

/// The MCP half of the `/api/health` contract, parsed — the Swift end of the
/// shape `tests/test_mcp_server.py::TestHealthAdvertisesMount` pins on the
/// Python end. A payload without the `mcp` block reads as (false, false):
/// a build that doesn't report the capability doesn't have it.
///
/// The server computes `active` ("tool call within the last two minutes")
/// itself, so the freshness window lives in exactly one place and the
/// auth-exempt health route never publishes an activity timeline.
enum AgentActivity {
    static func parse(_ json: [String: Any]?) -> (mounted: Bool, active: Bool) {
        guard let mcp = json?["mcp"] as? [String: Any] else { return (false, false) }
        return (mcp["mounted"] as? Bool ?? false, mcp["active"] as? Bool ?? false)
    }

    /// The per-serve `mcp.instance_id` nonce (fresh every start, stable
    /// within a serve). The handshake file carries it so the proxy can
    /// verify it is talking to this serve before transmitting the bearer.
    /// Nil on builds that predate it — the handshake is then unwritable,
    /// which fails safe (no file beats a file the proxy can't verify).
    static func instanceID(_ json: [String: Any]?) -> String? {
        guard let mcp = json?["mcp"] as? [String: Any] else { return nil }
        let iid = mcp["instance_id"] as? String
        return (iid?.isEmpty == false) ? iid : nil
    }

    /// Project-path identity for the connect sheet + badge. Bookmark healing
    /// (`refreshAvailability`) can respell `project.path` (`/private/…`,
    /// symlink resolution) while `currentProjectPath` holds the spawn-time
    /// string — raw equality then reads a running project as "not running"
    /// with no signal. Same standardisation `MCPTokenStore.accountKey` uses.
    static func samePath(_ a: String?, _ b: String) -> Bool {
        guard let a else { return false }
        return URL(fileURLWithPath: a).standardizedFileURL.path
            == URL(fileURLWithPath: b).standardizedFileURL.path
    }
}
