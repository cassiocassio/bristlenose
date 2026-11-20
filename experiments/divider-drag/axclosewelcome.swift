import ApplicationServices
import Foundation
let pid = pid_t(CommandLine.arguments[1])!
func attr(_ e: AXUIElement, _ a: String) -> CFTypeRef? { var v: CFTypeRef?; AXUIElementCopyAttributeValue(e, a as CFString, &v); return v }
for w in (attr(AXUIElementCreateApplication(pid), kAXWindowsAttribute) as? [AXUIElement]) ?? [] {
  if ((attr(w, kAXTitleAttribute) as? String) ?? "").hasPrefix("Welcome"), let b = attr(w, kAXCloseButtonAttribute) { print(AXUIElementPerformAction(b as! AXUIElement, kAXPressAction as CFString).rawValue) } }
