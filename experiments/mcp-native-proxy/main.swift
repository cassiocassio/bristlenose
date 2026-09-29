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
let MSG_AUTH = "Bristlenose refused this connection's stored credential. Tell the person to open Bristlenose ▸ Settings ▸ MCP Agents and check this project's agent access is turned on, then ask again. " + GROUNDING

// Tool list: compiled in (TOOLS_JSON, generated by build.sh from the Node
// proxy's BN-TOOLS-JSON block). A sandboxed proxy cannot read a file beside
// itself in another app's plugin folder, so nothing is loaded at runtime.
let TOOLS: Any = try! JSONSerialization.jsonObject(with: Data(TOOLS_JSON.utf8))

enum HS { case none, denied, ok([[String: Any]]) }
func readHandshake() -> HS {
    var denied = false
    for p in HANDSHAKES {
        let fd = open(p, O_RDONLY)
        if fd < 0 { if errno == EPERM || errno == EACCES { denied = true; log("handshake read denied errno=\(errno) \(p)") }; continue }
        let data = FileHandle(fileDescriptor: fd, closeOnDealloc: true).readDataToEndOfFile()
        guard let j = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { log("handshake unparseable \(p)"); continue }
        if let ps = j["projects"] as? [[String: Any]] { return .ok(ps) }
        if j["port"] != nil { return .ok([j]) }
        return .ok([])
    }
    return denied ? .denied : .none
}

func http(_ url: String, method: String = "GET", headers: [String: String] = [:], body: Data? = nil, timeout: Double) -> (Int, Data, String)? {
    var req = URLRequest(url: URL(string: url)!, timeoutInterval: timeout)
    req.httpMethod = method; req.httpBody = body
    headers.forEach { req.setValue($0.value, forHTTPHeaderField: $0.key) }
    let sem = DispatchSemaphore(value: 0); var out: (Int, Data, String)? = nil
    URLSession.shared.dataTask(with: req) { d, r, _ in
        if let h = r as? HTTPURLResponse { out = (h.statusCode, d ?? Data(), h.value(forHTTPHeaderField: "Content-Type") ?? "") }
        sem.signal()
    }.resume()
    sem.wait(); return out
}

func text(_ t: String) -> [String: Any] { ["content": [["type": "text", "text": t]]] }

func callTool(_ msg: [String: Any]) -> [String: Any] {
    let params = msg["params"] as? [String: Any] ?? [:]
    let name = params["name"] as? String ?? ""
    var args = params["arguments"] as? [String: Any] ?? [:]
    let wanted = args.removeValue(forKey: "project") as? String
    let hs = readHandshake()
    guard case .ok(let entries) = hs else {
        log("tool \(name): handshake \(hs.isDenied ? "DENIED" : "absent")")
        return text(hs.isDenied ? MSG_PERMISSION : MSG_CLOSED)
    }
    log("tool \(name): handshake ok, \(entries.count) project(s), project arg=\(wanted ?? "-")")
    if name == "list_projects" {
        let list = entries.compactMap { e -> [String: Any]? in (e["key"] as? String).map { ["key": $0, "name": e["name"] as? String ?? ""] } }
        if list.isEmpty { return text(MSG_CLOSED) }
        let d = try! JSONSerialization.data(withJSONObject: ["projects": list], options: [.prettyPrinted, .sortedKeys])
        return text(String(data: d, encoding: .utf8)!)
    }
    let readable = entries.map { "\($0["name"] as? String ?? "(unnamed)") = \($0["key"] as? String ?? "")" }.joined(separator: ", ")
    let entry: [String: Any]?
    if let w = wanted {
        entry = entries.first { $0["key"] as? String == w }
        if entry == nil {
            log("tool \(name): unknown project arg \(w)")
            return text("That project is not open in Bristlenose right now. Currently readable (name = key to pass as `project`): \(readable). " + GROUNDING)
        }
    } else if entries.count == 1 { entry = entries[0] }
    else {
        log("tool \(name): ambiguous, \(entries.count) projects")
        return text("Bristlenose has more than one project open, so this question needs one named. Ask the person which they mean, then pass its `project` key: \(readable). " + GROUNDING)
    }
    guard let e = entry, let port = e["port"] as? Int, let token = e["token"] as? String else {
        log("tool \(name): entry missing port/token"); return text(MSG_CLOSED)
    }
    // Unauthenticated probe first: never send the bearer to an unverified port.
    guard let (hsStatus, hBody, _) = http("http://127.0.0.1:\(port)/api/health", timeout: 1.5) else { return text(MSG_STARTING) }
    let health = (try? JSONSerialization.jsonObject(with: hBody)) as? [String: Any]
    let mcp = health?["mcp"] as? [String: Any]
    guard hsStatus == 200, let iid = e["instance_id"] as? String, mcp?["instance_id"] as? String == iid else {
        log("tool \(name): probe rejected status=\(hsStatus) instance match=\(mcp?["instance_id"] as? String == e["instance_id"] as? String)")
        return text(MSG_CLOSED)
    }
    let body = try! JSONSerialization.data(withJSONObject: ["jsonrpc": "2.0", "id": msg["id"] ?? 0, "method": "tools/call",
                                                            "params": ["name": name, "arguments": args]])
    guard let (st, d, ct) = http("http://127.0.0.1:\(port)/mcp/", method: "POST",
        headers: ["Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                  "Authorization": "Bearer \(token)", "X-Bristlenose-Proxy-Contract": "2",
                  "X-Bristlenose-Proxy-Version": "0.0.5-native-spike"], body: body, timeout: 60) else { return text(MSG_STARTING) }
    if st == 401 { return text(MSG_AUTH) }
    var payload = d
    if ct.contains("text/event-stream"), let s = String(data: d, encoding: .utf8),
       let line = s.split(separator: "\n").first(where: { $0.hasPrefix("data:") }) {
        payload = Data(line.dropFirst(5).trimmingCharacters(in: .whitespaces).utf8)
    }
    if let j = (try? JSONSerialization.jsonObject(with: payload)) as? [String: Any] {
        if let r = j["result"] as? [String: Any] { return r }
        if let m = (j["error"] as? [String: Any])?["message"] as? String { return text(m + " " + GROUNDING) }
    }
    return text("Bristlenose answered with an unexpected error (HTTP \(st)), so there is no study data for this question. " + GROUNDING)
}
extension HS { var isDenied: Bool { if case .denied = self { return true }; return false } }

func handle(_ msg: [String: Any]) -> [String: Any] {
    switch msg["method"] as? String ?? "" {
    case "initialize": return ["protocolVersion": "2025-06-18", "capabilities": ["tools": ["listChanged": true]],
                               "serverInfo": ["name": "bristlenose", "version": "0.0.5-native-spike"]]
    case "tools/list": return ["tools": TOOLS]
    case "tools/call": return callTool(msg)
    default: return [:]
    }
}

log("started (disclaimed=\(ProcessInfo.processInfo.environment["BN_MCP_DISCLAIMED"] ?? "0"), pid \(getpid()))")
setvbuf(stdout, nil, _IOLBF, 0)
while let line = readLine(strippingNewline: true) {
    let t = line.trimmingCharacters(in: .whitespaces); if t.isEmpty { continue }
    guard let msg = (try? JSONSerialization.jsonObject(with: Data(t.utf8))) as? [String: Any] else { log("dropped unparseable frame"); continue }
    let result = handle(msg)
    guard let id = msg["id"] else { continue }
    let out = try! JSONSerialization.data(withJSONObject: ["jsonrpc": "2.0", "id": id, "result": result])
    FileHandle.standardOutput.write(out); FileHandle.standardOutput.write("\n".data(using: .utf8)!)
}
