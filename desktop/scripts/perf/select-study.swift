// Selects a sidebar row of a running app by (case-insensitive) substring, through the
// Accessibility tree, so a profiled copy opens on a rendered report and not on Welcome.
//   select-study <pid> [substring] [--wait-web]   with no substring: lists the rows.
//   --wait-web[=SECONDS]: after selecting, wait up to 20 s (or SECONDS) for a rendered web area (the report) and exit 5
//   if there is none, so a profile can never silently measure an empty detail pane.
import ApplicationServices
import Foundation

func attr(_ e: AXUIElement, _ a: String) -> CFTypeRef? { var v: CFTypeRef?; AXUIElementCopyAttributeValue(e, a as CFString, &v); return v }
func kids(_ e: AXUIElement) -> [AXUIElement] { (attr(e, kAXChildrenAttribute) as? [AXUIElement]) ?? [] }
func texts(_ e: AXUIElement, _ depth: Int = 0) -> [String] {
    var out: [String] = []
    if let v = attr(e, kAXValueAttribute) as? String, !v.isEmpty { out.append(v) }
    if let t = attr(e, kAXTitleAttribute) as? String, !t.isEmpty { out.append(t) }
    if depth < 5 { for c in kids(e) { out += texts(c, depth + 1) } }
    return out
}
func find(_ e: AXUIElement, role: String, depth: Int = 0) -> AXUIElement? {
    if (attr(e, kAXRoleAttribute) as? String) == role { return e }
    if depth > 9 { return nil }
    for c in kids(e) { if let f = find(c, role: role, depth: depth + 1) { return f } }
    return nil
}
guard CommandLine.arguments.count >= 2, let pid = Int32(CommandLine.arguments[1]) else { print("usage: select-study <pid> [substring]"); exit(2) }
guard let outline = find(AXUIElementCreateApplication(pid), role: "AXOutline") else { print("{\"error\":\"no sidebar outline\"}"); exit(3) }
let rows = (attr(outline, kAXRowsAttribute) as? [AXUIElement]) ?? []
let labels = rows.map { texts($0).joined(separator: " | ") }
guard CommandLine.arguments.count >= 3 else { for (i, l) in labels.enumerated() { print("\(i): \(l)") }; exit(0) }
let needle = CommandLine.arguments[2].lowercased()
guard let i = labels.firstIndex(where: { $0.lowercased().contains(needle) }) else { print("{\"error\":\"no row matching \(needle)\"}"); exit(4) }
let ok = AXUIElementSetAttributeValue(outline, kAXSelectedRowsAttribute as CFString, [rows[i]] as CFArray) == .success
var web = ""
if let flag = CommandLine.arguments.first(where: { $0.hasPrefix("--wait-web") }) {
    let patience = Double(flag.split(separator: "=").dropFirst().first ?? "20") ?? 20
    func webArea(_ e: AXUIElement, _ d: Int = 0) -> String? {
        if (attr(e, kAXRoleAttribute) as? String) == "AXWebArea" { return (attr(e, kAXTitleAttribute) as? String) ?? "" }
        if d > 16 { return nil }
        for c in kids(e) { if let t = webArea(c, d + 1) { return t } }
        return nil
    }
    let app = AXUIElementCreateApplication(pid)
    let deadline = Date().addingTimeInterval(patience)
    var found: String?
    while found == nil && Date() < deadline { found = webArea(app); if found == nil { Thread.sleep(forTimeInterval: 0.5) } }
    guard let t = found else { print("{\"error\":\"no web area rendered after selecting\"}"); exit(5) }
    web = ",\"web_area\":\"\(t.replacingOccurrences(of: "\"", with: "'"))\""
}
print("{\"selected\":\"\(labels[i].replacingOccurrences(of: "\"", with: "'"))\",\"ok\":\(ok)\(web)}")
