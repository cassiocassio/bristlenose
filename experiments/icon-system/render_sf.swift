// Render SF Symbols to PNG for side-by-side weight comparison in a mockup.
// usage: swift render.swift <outdir> <pointSize> <weights,comma> <name> [<name>...]
// Writes <outdir>/<name>@<weight>-<pt>.png at 2x, black on transparent.
import AppKit

let args = CommandLine.arguments
guard args.count >= 5 else { print("usage: outdir pt weights names..."); exit(2) }
let outDir = URL(fileURLWithPath: args[1])
let pt = CGFloat(Double(args[2])!)
let weightMap: [String: NSFont.Weight] = [
    "ultralight": .ultraLight, "thin": .thin, "light": .light, "regular": .regular,
    "medium": .medium, "semibold": .semibold, "bold": .bold, "heavy": .heavy, "black": .black,
]
let weights = args[3].split(separator: ",").map(String.init)
try? FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)
var missing: [String] = []
for name in args[4...] {
    guard let base = NSImage(systemSymbolName: name, accessibilityDescription: nil) else {
        missing.append(name); continue
    }
    for w in weights {
        let cfg = NSImage.SymbolConfiguration(pointSize: pt, weight: weightMap[w]!)
            .applying(.init(hierarchicalColor: .black))
        guard let img = base.withSymbolConfiguration(cfg) else { continue }
        let size = img.size
        let scale: CGFloat = 2
        let rep = NSBitmapImageRep(
            bitmapDataPlanes: nil, pixelsWide: Int(ceil(size.width * scale)),
            pixelsHigh: Int(ceil(size.height * scale)), bitsPerSample: 8, samplesPerPixel: 4,
            hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
        rep.size = size
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
        img.draw(in: NSRect(origin: .zero, size: size))
        NSGraphicsContext.restoreGraphicsState()
        let png = rep.representation(using: .png, properties: [:])!
        let file = outDir.appendingPathComponent("\(name)@\(w)-\(Int(pt)).png")
        try! png.write(to: file)
        print("\(name) \(w) \(Int(pt))pt \(size.width)x\(size.height)")
    }
}
if !missing.isEmpty { print("MISSING: \(missing.joined(separator: " "))") }
