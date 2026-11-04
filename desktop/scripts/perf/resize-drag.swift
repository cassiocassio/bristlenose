// Drags the right edge of a running app's window back and forth with a real mouse
// (CGEvent), so AppKit sees a genuine live resize: the notifications, the per-frame
// layout and the WKWebView follow-along all happen. NSWindow.setFrame in a loop is not
// the same thing and would not exercise the live-resize path.
//
//   resize-drag <pid> [seconds=10] [minWidth=900] [maxWidth=1500] [hz=120]
//
// Needs Accessibility trust for the calling process. Moves the real pointer for the
// duration, so run it while nobody is using the Mac; the pointer is put back at the end.
// Prints one JSON line: window bounds before/after, widths seen, events posted.
import AppKit
import CoreGraphics
import Foundation

func windowBounds(_ pid: Int32) -> CGRect? {
    let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly], kCGNullWindowID) as? [[String: Any]] ?? []
    var best: CGRect?
    for w in list where (w[kCGWindowOwnerPID as String] as? Int32) == pid
        && (w[kCGWindowLayer as String] as? Int) == 0 {
        guard let d = w[kCGWindowBounds as String] as? NSDictionary,
              let r = CGRect(dictionaryRepresentation: d) else { continue }
        if best == nil || r.width * r.height > best!.width * best!.height { best = r }
    }
    return best
}

let args = CommandLine.arguments
guard args.count >= 2, let pid = Int32(args[1]) else {
    FileHandle.standardError.write(Data("usage: resize-drag <pid> [seconds] [amplitude] [hz]\n".utf8)); exit(2)
}
let seconds = args.count > 2 ? Double(args[2]) ?? 10 : 10
let minWidth = args.count > 3 ? Double(args[3]) ?? 900 : 900
let maxWidth = args.count > 4 ? Double(args[4]) ?? 1500 : 1500
let hz = args.count > 5 ? Double(args[5]) ?? 120 : 120

guard AXIsProcessTrusted() else {
    print("{\"error\":\"process is not Accessibility-trusted\"}"); exit(3)
}
NSRunningApplication(processIdentifier: pid)?.activate()
Thread.sleep(forTimeInterval: 0.6)
// Every run starts from the same frame, wherever the app last left its window: the width
// range of a drag decides which fit-to-width steps the layout goes through.
func setStartFrame(_ pid: Int32, width: Double, height: Double) {
    let app = AXUIElementCreateApplication(pid)
    var v: CFTypeRef?
    guard AXUIElementCopyAttributeValue(app, kAXWindowsAttribute as CFString, &v) == .success,
          let all = v as? [AXUIElement] else { return }
    // The app can have a small non-resizable panel too: take the window that can be sized.
    func area(_ e: AXUIElement) -> Double {
        var s: CFTypeRef?; var settable: DarwinBoolean = false
        AXUIElementIsAttributeSettable(e, kAXSizeAttribute as CFString, &settable)
        guard settable.boolValue, AXUIElementCopyAttributeValue(e, kAXSizeAttribute as CFString, &s) == .success,
              let s else { return 0 }
        var z = CGSize.zero; AXValueGetValue(s as! AXValue, .cgSize, &z); return Double(z.width * z.height)
    }
    guard let w = all.max(by: { area($0) < area($1) }), area(w) > 0 else { return }
    var pos = CGPoint(x: 40, y: 40), size = CGSize(width: width, height: height)
    if let p = AXValueCreate(.cgPoint, &pos) { AXUIElementSetAttributeValue(w, kAXPositionAttribute as CFString, p) }
    if let z = AXValueCreate(.cgSize, &size) { AXUIElementSetAttributeValue(w, kAXSizeAttribute as CFString, z) }
}
let startWidth = (minWidth + maxWidth) / 2
setStartFrame(pid, width: startWidth, height: 1000)
Thread.sleep(forTimeInterval: 0.8)
guard let start = windowBounds(pid) else { print("{\"error\":\"no on-screen window for pid \(pid)\"}"); exit(4) }

let screen = CGDisplayBounds(CGMainDisplayID())
let originalPointer = CGEvent(source: nil)?.location ?? .zero
// The edge: grab 2 pt inside the right border, halfway down, clear of the toolbar buttons.
let grabX = start.maxX - 2
let grabY = start.midY
// The drag goes between minWidth and maxWidth (as offsets from the start width), clamped
// to the screen.
let lo = minWidth - start.width
let hi = min(maxWidth - start.width, screen.maxX - 8 - start.maxX)

func post(_ type: CGEventType, _ x: Double, _ y: Double) {
    CGEvent(mouseEventSource: nil, mouseType: type, mouseCursorPosition: CGPoint(x: x, y: y),
            mouseButton: .left)?.post(tap: .cghidEventTap)
}
post(.mouseMoved, grabX, grabY); Thread.sleep(forTimeInterval: 0.15)
post(.leftMouseDown, grabX, grabY); Thread.sleep(forTimeInterval: 0.05)

// What the researcher feels is how often the window actually takes a new size, not how busy
// the main thread was. A sampler polls the window's width and records each change.
final class Sampler {
    var changes: [Double] = []; var running = true; private var last = -1.0
    func run(_ pid: Int32, _ t0: Date) {
        while running {
            if let b = windowBounds(pid), b.width != last { last = b.width; changes.append(Date().timeIntervalSince(t0)) }
            Thread.sleep(forTimeInterval: 0.002)
        }
    }
}
let sampler = Sampler()
let sampleT0 = Date()
let samplerThread = Thread { sampler.run(pid, sampleT0) }
samplerThread.start()

var posted = 0
let period = 2.5                         // seconds per full out-and-back
let step = 1.0 / hz
let t0 = Date()
var minW = start.width, maxW = start.width
while true {
    let t = Date().timeIntervalSince(t0)
    if t >= seconds { break }
    // Triangle wave between lo and hi, so every frame is a size change.
    let phase = (t / period).truncatingRemainder(dividingBy: 1.0)
    let tri = phase < 0.5 ? phase * 2 : (1 - phase) * 2
    let dx = lo + (hi - lo) * tri
    post(.leftMouseDragged, grabX + dx, grabY)
    posted += 1
    if posted % 30 == 0, let b = windowBounds(pid) { minW = min(minW, b.width); maxW = max(maxW, b.width) }
    Thread.sleep(forTimeInterval: step)
}
post(.leftMouseUp, grabX, grabY)
sampler.running = false
Thread.sleep(forTimeInterval: 0.3)
let end = windowBounds(pid) ?? start
post(.mouseMoved, originalPointer.x, originalPointer.y)

func r(_ v: Double) -> Double { (v * 10).rounded() / 10 }
let ch = sampler.changes.filter { $0 > 0.2 }               // drop the grab itself
let gaps = zip(ch.dropFirst(), ch).map { ($0 - $1) * 1000 }.sorted()
func pct(_ p: Double) -> Double { gaps.isEmpty ? 0 : gaps[min(gaps.count - 1, Int(Double(gaps.count) * p))] }
let rate = ch.count > 1 ? Double(ch.count - 1) / (ch.last! - ch.first!) : 0
print("{\"start_width\":\(r(start.width)),\"end_width\":\(r(end.width)),\"min_width_seen\":\(r(minW)),"
      + "\"max_width_seen\":\(r(maxW)),\"size_updates\":\(ch.count),\"updates_per_s\":\(r(rate)),"
      + "\"gap_p50_ms\":\(r(pct(0.5))),\"gap_p95_ms\":\(r(pct(0.95))),\"gap_max_ms\":\(r(gaps.last ?? 0)),\"events\":\(posted),\"seconds\":\(r(seconds)),\"moved\":\(minW != maxW)}")
