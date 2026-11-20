import ApplicationServices
import Foundation
let pid = pid_t(CommandLine.arguments[1])!; var s = CGSize(width: Double(CommandLine.arguments[2])!, height: Double(CommandLine.arguments[3])!)
let ax = AXUIElementCreateApplication(pid); var v: CFTypeRef?
AXUIElementCopyAttributeValue(ax, kAXWindowsAttribute as CFString, &v)
for w in (v as? [AXUIElement]) ?? [] { var t: CFTypeRef?; AXUIElementCopyAttributeValue(w, kAXTitleAttribute as CFString, &t)
  if ((t as? String) ?? "").hasPrefix("") { let r = AXUIElementSetAttributeValue(w, kAXSizeAttribute as CFString, AXValueCreate(.cgSize, &s)!); print("set", r.rawValue) } }
