// Posts N real left clicks at one point inside a running app's window, spaced apart, so a
// trace can show what each click costs the main thread (every mouse-down runs the window's
// local event monitors). Needs Accessibility trust; moves the pointer while it runs.
//   click-storm <pid> [count=40] [interval_ms=150]
import AppKit
import CoreGraphics
import Foundation

let args = CommandLine.arguments
guard args.count >= 2, let pid = Int32(args[1]) else { print("usage: click-storm <pid> [count] [interval_ms]"); exit(2) }
let count = args.count > 2 ? Int(args[2]) ?? 40 : 40
let gap = (args.count > 3 ? Double(args[3]) ?? 150 : 150) / 1000
guard AXIsProcessTrusted() else { print("{\"error\":\"not Accessibility-trusted\"}"); exit(3) }
NSRunningApplication(processIdentifier: pid)?.activate()
Thread.sleep(forTimeInterval: 0.6)
let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly], kCGNullWindowID) as? [[String: Any]] ?? []
var best: CGRect?
for w in list where (w[kCGWindowOwnerPID as String] as? Int32) == pid && (w[kCGWindowLayer as String] as? Int) == 0 {
    if let d = w[kCGWindowBounds as String] as? NSDictionary, let r = CGRect(dictionaryRepresentation: d),
       best == nil || r.width * r.height > best!.width * best!.height { best = r }
}
guard let b = best else { print("{\"error\":\"no window\"}"); exit(4) }
// Inside the detail pane, below the toolbar, clear of the sidebar: the report's heading area.
let x = b.minX + b.width * 0.62, y = b.minY + 150
let original = CGEvent(source: nil)?.location ?? .zero
for _ in 0..<count {
    for t in [CGEventType.leftMouseDown, .leftMouseUp] {
        CGEvent(mouseEventSource: nil, mouseType: t, mouseCursorPosition: CGPoint(x: x, y: y), mouseButton: .left)?.post(tap: .cghidEventTap)
        Thread.sleep(forTimeInterval: 0.02)
    }
    Thread.sleep(forTimeInterval: gap)
}
CGEvent(mouseEventSource: nil, mouseType: .mouseMoved, mouseCursorPosition: original, mouseButton: .left)?.post(tap: .cghidEventTap)
print("{\"clicks\":\(count)}")
