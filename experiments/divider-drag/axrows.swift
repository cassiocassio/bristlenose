import AppKit
import ApplicationServices
let pid = pid_t(CommandLine.arguments[1])!
let ax = AXUIElementCreateApplication(pid)
func attr(_ e: AXUIElement, _ a: String) -> CFTypeRef? { var v: CFTypeRef?; AXUIElementCopyAttributeValue(e, a as CFString, &v); return v }
func rect(_ e: AXUIElement) -> CGRect? { var p = CGPoint.zero, s = CGSize.zero
  guard let pv = attr(e, kAXPositionAttribute), let sv = attr(e, kAXSizeAttribute) else { return nil }
  AXValueGetValue(pv as! AXValue, .cgPoint, &p); AXValueGetValue(sv as! AXValue, .cgSize, &s); return CGRect(origin: p, size: s) }
func text(_ e: AXUIElement) -> String { if let t = attr(e, kAXTitleAttribute) as? String, !t.isEmpty { return t }
  if let ch = attr(e, kAXChildrenAttribute) as? [AXUIElement] { for c in ch { let t = text(c); if !t.isEmpty { return t } } }
  return (attr(e, kAXValueAttribute) as? String) ?? "" }
func walk(_ e: AXUIElement, _ d: Int) { if d > 12 { return }
  if (attr(e, kAXRoleAttribute) as? String) == "AXRow", let r = rect(e) { print("row", Int(r.minX), Int(r.minY), Int(r.width), Int(r.height), text(e)) }
  if let ch = attr(e, kAXChildrenAttribute) as? [AXUIElement] { for c in ch { walk(c, d + 1) } } }
for w in (attr(ax, kAXWindowsAttribute) as? [AXUIElement]) ?? [] { print("WINDOW", attr(w, kAXTitleAttribute) as? String ?? "", rect(w).map{"\($0)"} ?? ""); walk(w, 0) }
