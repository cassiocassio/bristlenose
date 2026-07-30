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
}
