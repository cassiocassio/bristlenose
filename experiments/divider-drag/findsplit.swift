// findsplit <bundle-or-pid-name> : print AX splitters (x,y,w,h) and window frame of the app's front window.
import AppKit
import ApplicationServices
let name = CommandLine.arguments[1]
guard let app = NSWorkspace.shared.runningApplications.first(where: { $0.localizedName == name && $0.bundleURL?.path.contains("divider-lab") == true }) else { print("{\"error\":\"app not running\"}"); exit(3) }
let ax = AXUIElementCreateApplication(app.processIdentifier)
func attr(_ e: AXUIElement, _ a: String) -> CFTypeRef? { var v: CFTypeRef?; AXUIElementCopyAttributeValue(e, a as CFString, &v); return v }
func rect(_ e: AXUIElement) -> CGRect? {
  var p = CGPoint.zero, s = CGSize.zero
  guard let pv = attr(e, kAXPositionAttribute), let sv = attr(e, kAXSizeAttribute) else { return nil }
  AXValueGetValue(pv as! AXValue, .cgPoint, &p); AXValueGetValue(sv as! AXValue, .cgSize, &s); return CGRect(origin: p, size: s)
}
var out: [[String: Any]] = []
func walk(_ e: AXUIElement, _ d: Int) {
  if d > 14 { return }
  let role = attr(e, kAXRoleAttribute) as? String ?? ""
  if role == "AXSplitter" || role == "AXSplitGroup" || role == "AXWebArea", let r = rect(e) { out.append(["role": role, "x": r.minX, "y": r.minY, "w": r.width, "h": r.height]) }
  if let ch = attr(e, kAXChildrenAttribute) as? [AXUIElement] { for c in ch { walk(c, d + 1) } }
}
guard let wins = attr(ax, kAXWindowsAttribute) as? [AXUIElement], !wins.isEmpty else { print("{\"error\":\"no window\"}"); exit(3) }
var titles: [String] = []
for w in wins { titles.append(attr(w, kAXTitleAttribute) as? String ?? "?"); walk(w, 0) }
let wr = rect(wins[0])!
let d = try! JSONSerialization.data(withJSONObject: ["pid": app.processIdentifier, "titles": titles, "window": ["x": wr.minX, "y": wr.minY, "w": wr.width, "h": wr.height], "found": out], options: [.prettyPrinted])
print(String(data: d, encoding: .utf8)!)
