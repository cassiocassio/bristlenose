// Measure the stem of a lowercase "l" in the system font (SF Pro) at the house's
// CSS weights, as a fraction of the font size — the number an icon's stroke must
// equal to carry the same ink as the text beside it.
// usage: swift experiments/icon-system/measure_stems.swift
import AppKit
import CoreText

let size: CGFloat = 400
let weights: [CGFloat] = [370, 420, 490, 520, 600, 700]
let wght: UInt32 = 0x7767_6874  // 'wght'

let base = NSFont.systemFont(ofSize: size)
if let axes = CTFontCopyVariationAxes(base as CTFont) as? [[String: Any]] {
    for a in axes where (a[kCTFontVariationAxisIdentifierKey as String] as? UInt32) == wght {
        print("SF wght axis:", a[kCTFontVariationAxisMinimumValueKey as String] ?? "?", "…",
              a[kCTFontVariationAxisMaximumValueKey as String] ?? "?",
              "default", a[kCTFontVariationAxisDefaultValueKey as String] ?? "?")
    }
}

let opsz: UInt32 = 0x6F70_737A  // 'opsz'
if let axes = CTFontCopyVariationAxes(base as CTFont) as? [[String: Any]] {
    for a in axes where (a[kCTFontVariationAxisIdentifierKey as String] as? UInt32) == opsz {
        print("SF opsz axis:", a[kCTFontVariationAxisMinimumValueKey as String] ?? "?", "…",
              a[kCTFontVariationAxisMaximumValueKey as String] ?? "?")
    }
}

// Render at 400 pt for resolution, but with the optical size of the text being matched
// (WebKit picks the text cut at 13 px; Core Text would pick display at 400 pt).
func stem(_ w: CGFloat, optical: CGFloat? = nil) -> CGFloat {
    let desc = (base.fontDescriptor as CTFontDescriptor)
    var varied = CTFontDescriptorCreateCopyWithVariation(desc, NSNumber(value: wght), w)
    if let o = optical { varied = CTFontDescriptorCreateCopyWithVariation(varied, NSNumber(value: opsz), o) }
    let font = CTFontCreateWithFontDescriptor(varied, size, nil)
    let W = 600, H = 600
    let ctx = CGContext(data: nil, width: W, height: H, bitsPerComponent: 8, bytesPerRow: W,
                        space: CGColorSpaceCreateDeviceGray(), bitmapInfo: CGImageAlphaInfo.none.rawValue)!
    ctx.setFillColor(gray: 1, alpha: 1); ctx.fill(CGRect(x: 0, y: 0, width: W, height: H))
    let attr = NSAttributedString(string: "l", attributes: [.font: font, .foregroundColor: NSColor.black])
    let line = CTLineCreateWithAttributedString(attr)
    ctx.textPosition = CGPoint(x: 100, y: 150)
    CTLineDraw(line, ctx)
    let row = 300  // well inside the stem, away from the terminals
    let p = ctx.data!.assumingMemoryBound(to: UInt8.self)
    var ink: CGFloat = 0
    for x in 0..<W { ink += CGFloat(255 - p[row * W + x]) / 255 }
    return ink / size
}

print("weight  auto(400pt)  opsz11  opsz13  opsz15   → px at 13 (opsz13)")
for w in weights {
    let a = stem(w), o11 = stem(w, optical: 11), o13 = stem(w, optical: 13), o15 = stem(w, optical: 15)
    print(String(format: "%-6.0f  %.4f      %.4f  %.4f  %.4f   %.2f", w, a, o11, o13, o15, o13 * 13))
}
