// Spike: native Bristlenose MCP proxy (stdio JSON-RPC → local serve over HTTP).
// Port of the essentials of desktop/mcpb/server/index.js, for the ChatGPT
// plugin spike (29 Sep 2026). Two properties the Node proxy cannot have:
//   1. no runtime — nothing on the user's PATH is required;
//   2. on first start it re-launches itself with responsibility DISCLAIMED, so
//      the process that reads Bristlenose's container is its own responsible
//      process, signed by Bristlenose's team — a same-team read, which macOS 27
//      allows without a Files & Folders grant (measured 29 Sep 2026).
import Foundation
import Darwin

@_silgen_name("responsibility_spawnattrs_setdisclaim")
func responsibility_spawnattrs_setdisclaim(_ attrs: UnsafeMutablePointer<posix_spawnattr_t?>, _ disclaim: Int32) -> Int32

func log(_ s: String) { FileHandle.standardError.write(("[bn-proxy-native] " + s + "\n").data(using: .utf8)!) }

// Two builds from this file:
//   default          — disclaim variant: relaunches itself with responsibility
//                      disclaimed (private SPI; Developer ID only).
//   -D GROUP_VARIANT — App Store shape: sandboxed (entitlements), carries the
//                      Team-ID-prefixed app group, reads the handshake from the
//                      group container. No private SPI. See docs §6.
let GROUP_ID = "Z56GZVA2QB.app.bristlenose"

// --- Stage 1: re-launch disclaimed ------------------------------------------
#if !GROUP_VARIANT
if ProcessInfo.processInfo.environment["BN_MCP_DISCLAIMED"] != "1" {
    var attr: posix_spawnattr_t? = nil
    posix_spawnattr_init(&attr)
    let rc = responsibility_spawnattrs_setdisclaim(&attr, 1)
    let exe = CommandLine.arguments[0].hasPrefix("/") ? CommandLine.arguments[0]
        : FileManager.default.currentDirectoryPath + "/" + CommandLine.arguments[0]
    var env = ProcessInfo.processInfo.environment
    env["BN_MCP_DISCLAIMED"] = "1"
    let envp = env.map { strdup("\($0.key)=\($0.value)") } + [nil]
    let argv = CommandLine.arguments.map { strdup($0) } + [nil]
    var pid: pid_t = 0
    let e = posix_spawn(&pid, exe, nil, &attr, argv, envp)
    if e != 0 { log("disclaimed spawn failed errno=\(e) (setdisclaim rc=\(rc)); serving in-process"); }
    else {
        log("relaunched disclaimed as pid \(pid)")
        var st: Int32 = 0
        while waitpid(pid, &st, 0) < 0 && errno == EINTR {}
        exit((st >> 8) & 0xff)
    }
}
#endif

// --- Stage 2: the proxy -----------------------------------------------------
#if GROUP_VARIANT
// Sandboxed: HOME is the proxy's own container, so resolve the group through
// the API the entitlement authorises rather than building a path.
let groupDir = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: GROUP_ID)
let GROUP_HANDSHAKE = groupDir?.appendingPathComponent("Bristlenose/mcp-handshake.json").path
let HANDSHAKES = [GROUP_HANDSHAKE].compactMap { $0 }

// `--seed`: SPIKE ONLY. Stands in for the Bristlenose app writing the handshake
// into the group (the shipped app writes only to its data container today).
// Reads a handshake on stdin and writes it atomically, 0600, into the group.
if CommandLine.arguments.dropFirst().first == "--seed" {
    guard let dir = groupDir else { log("seed: no group container (entitlement missing?)"); exit(2) }
    let data = FileHandle.standardInput.readDataToEndOfFile()
    guard (try? JSONSerialization.jsonObject(with: data)) != nil else { log("seed: stdin is not JSON"); exit(3) }
    let sub = dir.appendingPathComponent("Bristlenose")
    do {
        try FileManager.default.createDirectory(at: sub, withIntermediateDirectories: true)
        let tmp = sub.appendingPathComponent(".mcp-handshake.tmp")
        FileManager.default.createFile(atPath: tmp.path, contents: data, attributes: [.posixPermissions: 0o600])
        _ = try FileManager.default.replaceItemAt(sub.appendingPathComponent("mcp-handshake.json"), withItemAt: tmp)
        log("seed: wrote \(data.count) bytes to \(sub.path)/mcp-handshake.json"); exit(0)
    } catch { log("seed failed: \(error)"); exit(4) }
}
#else
let home = FileManager.default.homeDirectoryForCurrentUser.path
let HANDSHAKES = [
    ProcessInfo.processInfo.environment["BRISTLENOSE_DEV_MCP_HANDSHAKE"],
    home + "/Library/Containers/app.bristlenose/Data/Library/Application Support/Bristlenose/mcp-handshake.json",
    home + "/Library/Application Support/Bristlenose/mcp-handshake.json",
].compactMap { $0 }
#endif
let HOST = ProcessInfo.processInfo.environment["BRISTLENOSE_MCP_HOST"] ?? "your AI app"
let GROUNDING = "Do not answer from memory or from general knowledge."
let MSG_CLOSED = "Bristlenose isn't open, so there is no study data available. Tell the person to open Bristlenose and select a project, then ask again. " + GROUNDING
let MSG_STARTING = "Bristlenose is starting — ask again in a moment. " + GROUNDING
#if GROUP_VARIANT
// Sandboxed: the sandbox refuses the path before TCC is asked, so no Files &
// Folders switch can help. The remedy is the extension itself.
let MSG_PERMISSION = "This Bristlenose extension can't reach Bristlenose's data. Tell the person to open Bristlenose ▸ Settings ▸ MCP Agents and install the extension again, or check for a Bristlenose update, then ask again. " + GROUNDING
#else
// Wording aligned with docs/design-mcp-files-and-folders.md §3.
let MSG_PERMISSION = "macOS has blocked \(HOST) from reading Bristlenose. On this version of macOS there is no prompt — the access stays off until the person turns it on. Tell the person to open System Settings ▸ Privacy & Security ▸ Files & Folders, expand \(HOST) in the list, and turn on Bristlenose, then ask again. Nothing in Bristlenose needs changing. " + GROUNDING
#endif
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
let VERSION = "0.0.6-native-spike"

// Tool list: compiled in (TOOLS_JSON, generated by build.sh from the Node
// proxy's BN-TOOLS-JSON block). A sandboxed proxy cannot read a file beside
// itself in another app's plugin folder, so nothing is loaded at runtime.
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
    if name == "list_projects" {
        let list = projectList(entries)
        noteReady(!list.isEmpty)
        if list.isEmpty { return text(MSG_CLOSED) }
        let d = try! JSONSerialization.data(withJSONObject: ["projects": list], options: [.prettyPrinted, .sortedKeys])
        return withScope(text(String(data: d, encoding: .utf8)!), scope)
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
    let r = http("http://127.0.0.1:\(port)/mcp/", method: "POST",
        headers: ["Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                  "Authorization": "Bearer \(token)", "X-Bristlenose-Proxy-Contract": String(CONTRACT),
                  "X-Bristlenose-Proxy-Version": VERSION], body: body, timeout: 60)
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

log("started (disclaimed=\(ProcessInfo.processInfo.environment["BN_MCP_DISCLAIMED"] ?? "0"), pid \(getpid()), handshake candidates \(HANDSHAKES.count))")
while let line = readLine(strippingNewline: true) {
    let t = line.trimmingCharacters(in: .whitespaces); if t.isEmpty { continue }
    guard let msg = (try? JSONSerialization.jsonObject(with: Data(t.utf8))) as? [String: Any] else { log("dropped unparseable frame"); continue }
    let result = handle(msg)
    if let id = msg["id"] { emit(["jsonrpc": "2.0", "id": id, "result": result]) }
}
