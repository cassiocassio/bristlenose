// drag <out.json> <seconds> <amplitude-pt> <hz> <drag|none>
// Waits for <out>.ready, then drags the divider back and forth with a real mouse (CGEvent).
// Pointer is put back where it was. Needs Accessibility trust.
import AppKit
import CoreGraphics
import Foundation

let a = CommandLine.arguments
guard a.count >= 6, let secs = Double(a[2]), let amp = Double(a[3]), let hz = Double(a[4]) else {
    print("usage: drag <out.json> <seconds> <amp> <hz> <drag|none>"); exit(2)
}
let out = a[1], kind = a[5]
let readyPath = out + ".ready"
var waited = 0.0
while !FileManager.default.fileExists(atPath: readyPath) {
    Thread.sleep(forTimeInterval: 0.2); waited += 0.2
    if waited > 120 { print("{\"error\":\"lab never became ready\"}"); exit(3) }
}
Thread.sleep(forTimeInterval: 0.5)
guard let d = try? Data(contentsOf: URL(fileURLWithPath: readyPath)),
      let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any],
      let x0 = j["x"] as? Double, let y0 = j["y"] as? Double else { print("{\"error\":\"bad ready file\"}"); exit(3) }
guard AXIsProcessTrusted() else { print("{\"error\":\"not Accessibility-trusted\"}"); exit(3) }

let original = CGEvent(source: nil)?.location ?? CGPoint(x: 0, y: 0)
func post(_ type: CGEventType, _ p: CGPoint) {
    CGEvent(mouseEventSource: nil, mouseType: type, mouseCursorPosition: p, mouseButton: .left)?.post(tap: .cghidEventTap)
}
// A click on an inactive window only activates it, so activate the lab first with a click in its sidebar.
let activate = CGPoint(x: x0 - 150, y: y0)
post(.mouseMoved, activate); Thread.sleep(forTimeInterval: 0.2)
post(.leftMouseDown, activate); Thread.sleep(forTimeInterval: 0.05)
post(.leftMouseUp, activate); Thread.sleep(forTimeInterval: 0.6)
FileManager.default.createFile(atPath: out + ".start", contents: Data())
Thread.sleep(forTimeInterval: 0.3)   // let the lab begin recording
let t0 = Date()
var posted = 0
if kind == "drag" {
    post(.mouseMoved, CGPoint(x: x0, y: y0)); Thread.sleep(forTimeInterval: 0.25)
    post(.leftMouseDown, CGPoint(x: x0, y: y0)); Thread.sleep(forTimeInterval: 0.05)
    let period = 2.5, step = 1.0 / hz
    var next = Date().timeIntervalSince1970
    let start = next
    while next - start < secs {
        let t = next - start
        let x = x0 + amp * sin(2 * Double.pi * t / period)
        post(.leftMouseDragged, CGPoint(x: x, y: y0)); posted += 1
        next += step
        let wait = next - Date().timeIntervalSince1970
        if wait > 0 { Thread.sleep(forTimeInterval: wait) }
    }
    post(.leftMouseUp, CGPoint(x: x0, y: y0))
} else {
    Thread.sleep(forTimeInterval: secs)
}
Thread.sleep(forTimeInterval: 0.3)
FileManager.default.createFile(atPath: out + ".stop", contents: Data())
CGWarpMouseCursorPosition(original)
print("{\"posted_events\":\(posted),\"seconds\":\(Date().timeIntervalSince(t0)),\"kind\":\"\(kind)\"}")
