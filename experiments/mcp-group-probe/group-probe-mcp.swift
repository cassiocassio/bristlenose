// Group-route probe: a minimal stdio MCP server with one tool, `group_probe`.
// It reports who is responsible for it and whether it can use the team-prefixed
// app group container. No private API is called except responsibility_get_pid_responsible_for_pid,
// which is diagnostics only (this is a probe, not the shipping proxy).
import Foundation
import Darwin

@_silgen_name("responsibility_get_pid_responsible_for_pid")
func responsibleFor(_ pid: pid_t) -> pid_t

let group = "Z56GZVA2QB.app.bristlenose.probe"

func path(of pid: pid_t) -> String {
    var buf = [CChar](repeating: 0, count: 4096)
    return proc_pidpath(pid, &buf, UInt32(buf.count)) > 0 ? String(cString: buf) : "?"
}

func probe() -> String {
    var lines: [String] = []
    let me = getpid(), r = responsibleFor(me)
    lines.append("variant=\(Bundle.main.bundleIdentifier ?? "none") sandboxed=\(ProcessInfo.processInfo.environment["APP_SANDBOX_CONTAINER_ID"] != nil)")
    lines.append("pid=\(me) ppid=\(getppid()) (\(path(of: getppid())))")
    lines.append("responsible=\(r) (\(path(of: r)))")
    let fm = FileManager.default
    let base = fm.homeDirectoryForCurrentUser.path  // inside a sandbox this is the container
    let home = NSHomeDirectoryForUser(NSUserName()) ?? base
    let g = URL(fileURLWithPath: home).appendingPathComponent("Library/Group Containers/\(group)")
    lines.append("containerURL(forSecurityApplicationGroupIdentifier:)=\(fm.containerURL(forSecurityApplicationGroupIdentifier: group)?.path ?? "nil")")
    let f = g.appendingPathComponent("probe-\(me).txt")
    do { try fm.createDirectory(at: g, withIntermediateDirectories: true); lines.append("MKDIR ok") } catch { lines.append("MKDIR \(error.localizedDescription)") }
    do { try "probe\n".write(to: f, atomically: false, encoding: .utf8); lines.append("WRITE ok") } catch { lines.append("WRITE \((error as NSError).code) \(error.localizedDescription)") }
    do { let s = try String(contentsOf: f, encoding: .utf8); lines.append("READ ok (\(s.count) chars)") } catch { lines.append("READ \(error.localizedDescription)") }
    do { try fm.removeItem(at: f); lines.append("UNLINK ok") } catch { lines.append("UNLINK \(error.localizedDescription)") }
    let data = URL(fileURLWithPath: home).appendingPathComponent("Library/Containers/app.bristlenose/Data/Library/Application Support/Bristlenose")
    do { let n = try fm.contentsOfDirectory(atPath: data.path).count; lines.append("DATA-CONTAINER LIST ok (\(n)) [expected denied when sandboxed]") } catch { lines.append("DATA-CONTAINER LIST denied: \(error.localizedDescription)") }
    return lines.joined(separator: "\n")
}

func send(_ obj: [String: Any]) {
    let d = try! JSONSerialization.data(withJSONObject: obj)
    FileHandle.standardOutput.write(d); FileHandle.standardOutput.write("\n".data(using: .utf8)!)
}

while let line = readLine() {
    guard let d = line.data(using: .utf8),
          let msg = (try? JSONSerialization.jsonObject(with: d)) as? [String: Any],
          let method = msg["method"] as? String else { continue }
    guard let id = msg["id"] else { continue }  // notifications
    switch method {
    case "initialize":
        let pv = ((msg["params"] as? [String: Any])?["protocolVersion"] as? String) ?? "2025-06-18"
        send(["jsonrpc": "2.0", "id": id, "result": ["protocolVersion": pv, "capabilities": ["tools": [:]],
              "serverInfo": ["name": "bristlenose-group-probe", "version": "0.0.1"]]])
    case "tools/list":
        send(["jsonrpc": "2.0", "id": id, "result": ["tools": [[
            "name": "group_probe",
            "description": "Diagnostic: report the responsible process and whether this binary can use its team app group container.",
            "inputSchema": ["type": "object", "properties": [:]],
            "annotations": ["readOnlyHint": true]]]]])
    case "tools/call":
        let text = probe()
        FileHandle.standardError.write(("group_probe:\n" + text + "\n").data(using: .utf8)!)
        send(["jsonrpc": "2.0", "id": id, "result": ["content": [["type": "text", "text": text]]]])
    case "ping":
        send(["jsonrpc": "2.0", "id": id, "result": [:]])
    default:
        send(["jsonrpc": "2.0", "id": id, "error": ["code": -32601, "message": "unknown method"]])
    }
}
