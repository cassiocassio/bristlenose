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

    /// This serve's stable project key from `mcp.project_key` — the digest
    /// Python computes from the resolved input path. Read, never re-derived:
    /// one implementation of the key means a citation cannot mean two things.
    /// Nil on builds that predate it, which simply keeps that project out of
    /// the handshake rather than exposing it under an unknown identity.
    static func projectKey(_ json: [String: Any]?) -> String? {
        guard let mcp = json?["mcp"] as? [String: Any] else { return nil }
        let key = mcp["project_key"] as? String
        return (key?.isEmpty == false) ? key : nil
    }

    /// The proxy's self-reported build, from the AUTHED `/api/agent-activity`
    /// payload (never `/api/health` — that route is auth-exempt and this
    /// describes the researcher's agent setup, not the server's liveness).
    ///
    /// Nil is NOT "out of date". It means no EXTENSION build has identified
    /// itself — which covers both "nothing has called yet" and "an agent
    /// called through the Generic MCP path", since a non-`.mcpb` client sends
    /// no header. Pair with the payload's `calls` to tell those apart; a
    /// serve nobody has queried must not read as stale either way.
    ///
    /// Diagnostic only. Compatibility is `mcp.contract`'s job — a `.mcpb`
    /// never auto-updates, so the proxy in the field is routinely older than
    /// the app and comparing release versions as a GATE would cry wolf on
    /// every patch (see `MCP_CONTRACT` in routes/health.py).
    static func proxyVersion(_ json: [String: Any]?) -> String? {
        let raw = json?["proxy_version"] as? String
        return (raw?.isEmpty == false) ? raw : nil
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
