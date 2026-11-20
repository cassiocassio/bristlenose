// drag2 <x0> <y0> <center> <amp> <seconds> <hz> : activates window with a click at (x0-120,y0), grabs divider, glides to center, oscillates, releases at x0+center. Prints epoch ms start/end of the oscillation.
import CoreGraphics
import Foundation
let a = CommandLine.arguments.dropFirst().map { Double($0)! }
let (x0, y0, center, amp, secs, hz) = (a[0], a[1], a[2], a[3], a[4], a[5])
let orig = CGEvent(source: nil)!.location
func post(_ t: CGEventType, _ x: Double, _ y: Double? = nil) { CGEvent(mouseEventSource: nil, mouseType: t, mouseCursorPosition: CGPoint(x: x, y: y ?? y0), mouseButton: .left)?.post(tap: .cghidEventTap) }
usleep(300000)
post(.mouseMoved, x0); usleep(250000); post(.leftMouseDown, x0); usleep(50000)
for i in 1...30 { post(.leftMouseDragged, x0 + center * Double(i) / 30); usleep(8000) }
usleep(300000)
let t0 = Date().timeIntervalSince1970; var next = t0
while next - t0 < secs {
  let t = next - t0
  post(.leftMouseDragged, x0 + center + amp * sin(2 * Double.pi * t / 2.5))
  next += 1 / hz; let w = next - Date().timeIntervalSince1970; if w > 0 { usleep(UInt32(w * 1e6)) }
}
let t1 = Date().timeIntervalSince1970
post(.leftMouseUp, x0 + center)
usleep(300000); CGWarpMouseCursorPosition(orig)
print("{\"start_ms\":\(t0*1000),\"end_ms\":\(t1*1000)}")
