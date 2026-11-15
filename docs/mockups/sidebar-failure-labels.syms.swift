import AppKit
NSApplication.shared.setActivationPolicy(.prohibited)
let names = ["xmark.circle.fill","exclamationmark.triangle.fill","info.circle","exclamationmark.triangle","stop.circle","key","externaldrive.badge.xmark","network.slash","folder"]
var out = "{"
for (i,n) in names.enumerated() {
  let cfg = NSImage.SymbolConfiguration(pointSize: 64, weight: .regular)
  guard let img = NSImage(systemSymbolName: n, accessibilityDescription: nil)?.withSymbolConfiguration(cfg) else { print("missing",n); continue }
  let s = img.size
  let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(s.width*2), pixelsHigh: Int(s.height*2), bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
  rep.size = s
  NSGraphicsContext.saveGraphicsState()
  NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
  img.draw(in: NSRect(origin: .zero, size: s))
  NSGraphicsContext.restoreGraphicsState()
  let png = rep.representation(using: .png, properties: [:])!
  out += (i>0 ? "," : "") + "\"\(n)\":[\(s.width),\(s.height),\"\(png.base64EncodedString())\"]"
}
out += "}"
try! out.write(toFile: "syms.json", atomically: true, encoding: .utf8)
