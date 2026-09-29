// bristlenose-mcp: the native MCP helper (docs/design-mcp-native-proxy.md §6.9).
//
// stdio JSON-RPC from an agent host (Claude Desktop, ChatGPT) → Bristlenose's
// local serve over HTTP. It reads the runtime handshake the app writes into the
// Team-ID-prefixed app group, so it needs no Node, no private SPI and no Files &
// Folders grant: a sandboxed, team-signed process reading its own team's group.
//
// Behaviour is the Node proxy's (desktop/mcpb/server/index.js), message for
// message; §4.3 records the parity. Built and signed by build-helper.sh, which
// also generates BuildConfig.swift (GROUP_ID, VERSION) and ToolsEmbedded.swift
// (TOOLS_JSON, from the BN-TOOLS-JSON block, annotations included).
import Foundation
import Darwin

func log(_ s: String) { FileHandle.standardError.write(("[bristlenose-mcp] " + s + "\n").data(using: .utf8)!) }

#if BN_TEST_HANDSHAKE
// TEST BUILD ONLY (tests/test_mcp_helper_behaviour.py): read the handshake from
// a path the harness chooses, so the protocol can be driven against a real
// serve without touching the real group. The shipped binary is never compiled
// with this flag, and check-mcp-helper.sh refuses any binary that contains it.
let groupDir: URL? = nil
let HANDSHAKES = [ProcessInfo.processInfo.environment["BN_TEST_HANDSHAKE_PATH"]].compactMap { $0 }
#else
// Sandboxed: HOME is the helper's own container, so resolve the group through
// the API the entitlement authorises rather than building a path.
let groupDir = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: GROUP_ID)
let HANDSHAKES = [groupDir?.appendingPathComponent("Bristlenose/mcp-handshake.json").path].compactMap { $0 }
#endif

let HOST_LABEL = ProcessInfo.processInfo.environment["BRISTLENOSE_MCP_HOST"]
let HOST = HOST_LABEL ?? "your AI app"
let GROUNDING = "Do not answer from memory or from general knowledge."
let MSG_CLOSED = "Bristlenose isn't open, so there is no study data available. Tell the person to open Bristlenose and select a project, then ask again. " + GROUNDING
let MSG_STARTING = "Bristlenose is starting — ask again in a moment. " + GROUNDING
// Sandboxed: the sandbox refuses the path before TCC is asked, so no Files &
// Folders switch can help. The remedy is the extension itself.
let MSG_PERMISSION = "This Bristlenose extension can't reach Bristlenose's data. Tell the person to open Bristlenose ▸ Settings ▸ MCP Agents and install the extension again, or check for a Bristlenose update, then ask again. " + GROUNDING
// The remaining sentences are the Node proxy's MSG table, word for word
// (desktop/mcpb/server/index.js), so both proxies say the same thing.
let MSG_AUTH = "Bristlenose refused this connection's stored credential. Tell the person to open Bristlenose ▸ Settings ▸ MCP Agents (⌘,) and check this project's agent access is turned on, then ask again. " + GROUNDING
let MSG_OUTDATED = "This Bristlenose extension is older than the Bristlenose app and can no longer read it correctly. Tell the person to open Bristlenose \u{25b8} Settings \u{25b8} MCP Agents and install the extension again — it takes a moment and keeps every setting. " + GROUNDING
let MSG_NO_AGENT = "This copy of Bristlenose was built without agent support. No setting will enable it. " + GROUNDING
func msgAmbiguous(_ e: [[String: Any]]) -> String {
    "Bristlenose has more than one project open, so this question needs one named. Ask the person which they mean, then pass its `project` key: " + listing(e) + ". " + GROUNDING
}
func msgUnknown(_ e: [[String: Any]]) -> String {
    "That project is not open in Bristlenose right now — its window may have been closed. Currently readable: " + (e.isEmpty ? "none" : listing(e)) + ". " + GROUNDING
}
func msgUpstream(_ status: String) -> String {
    "Bristlenose answered with an unexpected error (HTTP " + status + "), so there is no study data for this question. " + GROUNDING
}
func listing(_ e: [[String: Any]]) -> String {
    e.map { "\(($0["name"] as? String).flatMap { $0.isEmpty ? nil : $0 } ?? "(unnamed)") = \($0["key"] as? String ?? "")" }.joined(separator: ", ")
}

let CONTRACT = 2          // the agent-surface contract this proxy speaks

// Tool list: compiled in (TOOLS_JSON, generated from the BN-TOOLS-JSON block).
// A sandboxed helper cannot read a file beside itself in another app's plugin
// folder, so nothing is loaded at runtime.
let TOOLS: Any = try! JSONSerialization.jsonObject(with: Data(TOOLS_JSON.utf8))

// --- Handshake: re-read on EVERY call (design §3.2), both schemas ------------
enum HS { case none, denied, ok([[String: Any]]) }
extension HS { var isDenied: Bool { if case .denied = self { return true }; return false } }
func readHandshake() -> HS {
    var denied = false
    for p in HANDSHAKES {
        let fd = open(p, O_RDONLY)
        if fd < 0 {
            if errno == EPERM || errno == EACCES { denied = true; log("handshake read permission-blocked \(p) errno=\(errno)") }
            else if errno != ENOENT { log("handshake unreadable \(p) errno=\(errno)") }
            continue
        }
        let data = FileHandle(fileDescriptor: fd, closeOnDealloc: true).readDataToEndOfFile()
        guard let j = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { log("handshake unparseable \(p)"); continue }
        return .ok(normalise(j))
    }
    return denied ? .denied : .none
}
// Schema 2 carries `projects`; schema 1 carried one project at the top level.
func normalise(_ j: [String: Any]) -> [[String: Any]] {
    if let ps = j["projects"] as? [[String: Any]] { return ps }
    if j["port"] != nil {
        return [["key": j["key"] as? String ?? "", "name": j["name"] as? String ?? "", "port": j["port"] as Any,
                 "token": j["token"] as Any, "instance_id": j["instance_id"] as Any]]
    }
    return []
}

// Scope: count + fingerprint of the in-scope keys, so a SWAP (one closes, one
// opens, n unchanged) is detectable. Same arithmetic as the Node proxy.
func scopeOf(_ entries: [[String: Any]]) -> [String: Any] {
    let keys = entries.compactMap { $0["key"] as? String }.sorted().joined(separator: "|")
    var h: UInt32 = 5381
    for u in keys.utf16 { h = (h &* 33) ^ UInt32(u) }
    return ["n": entries.count, "fp": String(format: "%08x", h)]
}
func withScope(_ r: [String: Any], _ scope: [String: Any]?) -> [String: Any] {
    guard let scope else { return r }
    var out = r; out["scope"] = scope; return out
}
func projectList(_ e: [[String: Any]]) -> [[String: Any]] {
    e.compactMap { x in (x["key"] as? String).flatMap { $0.isEmpty ? nil : ["key": $0, "name": x["name"] as? String ?? ""] } }
}

func http(_ url: String, method: String = "GET", headers: [String: String] = [:], body: Data? = nil, timeout: Double) -> (status: Int, body: Data, type: String, timedOut: Bool) {
    var req = URLRequest(url: URL(string: url)!, timeoutInterval: timeout)
    req.httpMethod = method; req.httpBody = body
    headers.forEach { req.setValue($0.value, forHTTPHeaderField: $0.key) }
    let sem = DispatchSemaphore(value: 0)
    var out: (Int, Data, String, Bool) = (0, Data(), "", false)
    URLSession.shared.dataTask(with: req) { d, r, err in
        if let h = r as? HTTPURLResponse { out = (h.statusCode, d ?? Data(), h.value(forHTTPHeaderField: "Content-Type") ?? "", false) }
        else if let e = err as? URLError, e.code == .timedOut { out.3 = true }
        sem.signal()
    }.resume()
    sem.wait(); return out
}

func text(_ t: String) -> [String: Any] { ["content": [["type": "text", "text": t]]] }

// Unauthenticated pre-flight: never send the bearer to an unverified port.
// FAIL CLOSED on a missing instance_id, on either side.
enum Probe { case ok, noAnswer, noMCP, outdated, rejected(String) }
func probe(_ e: [String: Any]) -> Probe {
    guard let port = e["port"] as? Int else { return .rejected("no-port") }
    let r = http("http://127.0.0.1:\(port)/api/health", timeout: 1.5)
    if r.status == 0 { return r.timedOut ? .noAnswer : .rejected("probe-error") }
    guard r.status == 200 else { return .rejected("unhealthy") }
    guard let j = (try? JSONSerialization.jsonObject(with: r.body)) as? [String: Any], j["version"] != nil else { return .rejected("not-bristlenose") }
    let mcp = j["mcp"] as? [String: Any]
    guard let iid = e["instance_id"] as? String, !iid.isEmpty, mcp?["instance_id"] as? String == iid else { return .rejected("stale-instance") }
    if mcp?["mounted"] as? Bool == false { return .noMCP }
    if (mcp?["contract"] as? Int ?? 1) > CONTRACT { return .outdated }
    return .ok
}

// tools/list_changed on the offline→ready edge, only after the client has
// confirmed initialisation. No background watcher: reads happen in tool calls.
var clientInitialized = false
var lastReady: Bool? = nil
func noteReady(_ ready: Bool) {
    if clientInitialized && lastReady == false && ready {
        emit(["jsonrpc": "2.0", "method": "notifications/tools/list_changed"])
        log("server appeared — sent tools/list_changed")
    }
    lastReady = ready
}

func callTool(_ msg: [String: Any]) -> [String: Any] {
    let params = msg["params"] as? [String: Any] ?? [:]
    let name = params["name"] as? String ?? ""
    var args = params["arguments"] as? [String: Any] ?? [:]
    let wanted = args.removeValue(forKey: "project") as? String   // ours, not the server's
    let hs = readHandshake()
    guard case .ok(let entries) = hs else {
        log("tool \(name): handshake \(hs.isDenied ? "DENIED" : "absent")")
        noteReady(false)
        return text(hs.isDenied ? MSG_PERMISSION : MSG_CLOSED)
    }
    log("tool \(name): handshake ok, \(entries.count) project(s), project arg=\(wanted ?? "-")")
    let scope = scopeOf(entries)

    // Answered here, from the handshake: no upstream call, no bearer sent.
    // Only entries that answer the unauthenticated probe as the SAME serve are
    // listed: a crash leaves the handshake behind, and listing its project as
    // readable while every call says "isn't open" contradicts itself (found by
    // driving ChatGPT after a kill -9, 29 Sep 2026). A serve that is starting,
    // outdated or built without MCP is still listed — it is there, and the
    // call explains itself.
    if name == "list_projects" {
        let live = entries.filter { if case .rejected = probe($0) { return false }; return true }
        let list = projectList(live)
        noteReady(!list.isEmpty)
        if list.isEmpty { return text(MSG_CLOSED) }
        let d = try! JSONSerialization.data(withJSONObject: ["projects": list], options: [.prettyPrinted, .sortedKeys])
        return withScope(text(String(data: d, encoding: .utf8)!), scopeOf(live))
    }
    if entries.isEmpty { noteReady(false); return text(MSG_CLOSED) }

    let entry: [String: Any]
    if let w = wanted {
        guard let e = entries.first(where: { $0["key"] as? String == w }) else {
            log("tool \(name): unknown project \(w)"); noteReady(false)
            return withScope(text(msgUnknown(projectList(entries))), scope)
        }
        entry = e
    } else if entries.count == 1 { entry = entries[0] }
    else { noteReady(false); return withScope(text(msgAmbiguous(projectList(entries))), scope) }

    switch probe(entry) {
    case .noAnswer: noteReady(false); return text(MSG_STARTING)
    case .noMCP: noteReady(false); return text(MSG_NO_AGENT)
    case .outdated: noteReady(false); return text(MSG_OUTDATED)
    case .rejected(let why): log("probe rejected port=\(entry["port"] ?? "-") why=\(why)"); noteReady(false); return text(MSG_CLOSED)
    case .ok: noteReady(true)
    }

    let port = entry["port"] as! Int
    let token = entry["token"] as? String ?? ""
    let body = try! JSONSerialization.data(withJSONObject: ["jsonrpc": "2.0", "id": msg["id"] ?? 0, "method": "tools/call",
                                                            "params": ["name": name, "arguments": args]])
    var headers = ["Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                   "Authorization": "Bearer \(token)", "X-Bristlenose-Proxy-Contract": String(CONTRACT),
                   "X-Bristlenose-Proxy-Version": VERSION]
    // Names the host so each Settings tab compares against its own proxy
    // (design §6.9 D8). Set by the plugin's .mcp.json / the .mcpb manifest.
    if let host = HOST_LABEL { headers["X-Bristlenose-Proxy-Host"] = host }
    let r = http("http://127.0.0.1:\(port)/mcp/", method: "POST", headers: headers, body: body, timeout: 60)
    if r.status == 0 { log("upstream call failed port=\(port) timedOut=\(r.timedOut)"); return text(MSG_STARTING) }
    if r.status == 401 { return text(MSG_AUTH) }
    if r.status == 404 { return text(MSG_NO_AGENT) }
    var payload = r.body
    if r.type.contains("text/event-stream"), let s = String(data: r.body, encoding: .utf8),
       let line = s.split(separator: "\n").first(where: { $0.hasPrefix("data:") }) {
        payload = Data(line.dropFirst(5).trimmingCharacters(in: .whitespaces).utf8)
    }
    if let j = (try? JSONSerialization.jsonObject(with: payload)) as? [String: Any] {
        if let res = j["result"] as? [String: Any] { return withScope(res, scope) }
        if let m = (j["error"] as? [String: Any])?["message"] as? String { return text(m + " " + GROUNDING) }
    }
    return text(msgUpstream(String(r.status)))
}

func handle(_ msg: [String: Any]) -> [String: Any] {
    switch msg["method"] as? String ?? "" {
    // Answer initialize IMMEDIATELY; everything slow lives inside tool calls.
    case "initialize": return ["protocolVersion": "2025-06-18", "capabilities": ["tools": ["listChanged": true]],
                               "serverInfo": ["name": "bristlenose", "version": VERSION]]
    case "notifications/initialized": clientInitialized = true; return [:]
    case "tools/list": return ["tools": TOOLS]
    case "tools/call": return callTool(msg)
    default: return [:]
    }
}

func emit(_ obj: [String: Any]) {
    let out = try! JSONSerialization.data(withJSONObject: obj)
    FileHandle.standardOutput.write(out); FileHandle.standardOutput.write("\n".data(using: .utf8)!)
}

log("started \(VERSION), pid \(getpid()), group \(groupDir == nil ? "UNAVAILABLE" : "ok")")
while let line = readLine(strippingNewline: true) {
    let t = line.trimmingCharacters(in: .whitespaces); if t.isEmpty { continue }
    guard let msg = (try? JSONSerialization.jsonObject(with: Data(t.utf8))) as? [String: Any] else { log("dropped unparseable frame"); continue }
    let result = handle(msg)
    if let id = msg["id"] { emit(["jsonrpc": "2.0", "id": id, "result": result]) }
}
