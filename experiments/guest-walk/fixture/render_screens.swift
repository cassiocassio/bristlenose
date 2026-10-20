// render_screens.swift <out-dir> — three fake web pages as 1280x720 PNGs, for the
// walk's screens fixture. Each page shares the same browser chrome (the Screens
// lens filters chrome that repeats across frames) and carries enough distinct
// body text to be a text-dense frame for OCR. Built and run on the host; the
// fixture it feeds is generated, never committed as video.
import AppKit

struct Page { let title: String; let url: String; let heading: String; let body: [String] }

let pages = [
    Page(title: "Lumen Home", url: "lumen-store.example/", heading: "Light up every room",
         body: ["Shop by room: Living room, Kitchen, Bedroom, Office",
                "New this week: the Arc floor lamp in brushed brass",
                "Free delivery on orders over £50",
                "Search lamps, bulbs and shades",
                "Bestsellers", "Halo pendant £89", "Dune table lamp £45", "Orbit wall light £62",
                "Sign up for 10% off your first order"]),
    Page(title: "Arc floor lamp", url: "lumen-store.example/arc-floor-lamp", heading: "Arc floor lamp",
         body: ["£149 · Brushed brass · 180 cm",
                "Choose a finish: Brass, Black, White, Copper, Chrome, Bronze",
                "Choose a shade: Linen, Paper, Glass, Metal",
                "Choose a plug: UK, EU, US",
                "Bulb included: E27 LED, warm white",
                "Add to basket", "Delivery in 3 to 5 working days",
                "Reviews (128): 4.6 out of 5"]),
    Page(title: "Checkout", url: "lumen-store.example/checkout", heading: "Checkout",
         body: ["Step 2 of 4: Your details",
                "Email address", "Phone number (required)",
                "Delivery address", "Postcode", "Find address",
                "Order summary: Arc floor lamp £149, Delivery £0",
                "Total £149", "Continue to payment"]),
]

let out = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "."
let W = 1280, H = 720
for (i, p) in pages.enumerated() {
    let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: W, pixelsHigh: H, bitsPerSample: 8,
                               samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                               colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
    NSGraphicsContext.saveGraphicsState()
    // Top-left origin: flip the CTM and tell AppKit the context is flipped, or
    // every glyph is drawn mirrored (the first render was upside down).
    NSGraphicsContext.current = NSGraphicsContext(cgContext: NSGraphicsContext(bitmapImageRep: rep)!.cgContext, flipped: true)
    let flip = NSAffineTransform(); flip.translateX(by: 0, yBy: CGFloat(H)); flip.scaleX(by: 1, yBy: -1); flip.concat()
    NSColor.white.setFill(); NSRect(x: 0, y: 0, width: W, height: H).fill()
    // browser chrome: tab strip and address bar, the same on every page
    NSColor(white: 0.92, alpha: 1).setFill(); NSRect(x: 0, y: 0, width: W, height: 84).fill()
    func text(_ s: String, _ x: CGFloat, _ y: CGFloat, _ size: CGFloat, _ weight: NSFont.Weight = .regular,
              _ color: NSColor = .black) {
        let a: [NSAttributedString.Key: Any] = [.font: NSFont.systemFont(ofSize: size, weight: weight),
                                                .foregroundColor: color]
        NSAttributedString(string: s, attributes: a).draw(at: NSPoint(x: x, y: y))
    }
    text(p.title, 24, 12, 15, .medium)
    NSColor.white.setFill(); NSBezierPath(roundedRect: NSRect(x: 20, y: 44, width: CGFloat(W) - 40, height: 30),
                                          xRadius: 8, yRadius: 8).fill()
    text("https://" + p.url, 36, 49, 15, .regular, NSColor(white: 0.3, alpha: 1))
    // site header, also repeated
    text("LUMEN", 60, 108, 28, .heavy)
    text("Lamps   Bulbs   Shades   Sale   Basket (\(i == 0 ? 0 : 1))", 700, 116, 18)
    text(p.heading, 60, 176, 40, .bold)
    for (j, line) in p.body.enumerated() { text(line, 60, 246 + CGFloat(j) * 46, 24) }
    NSGraphicsContext.restoreGraphicsState()
    let png = rep.representation(using: .png, properties: [:])!
    try! png.write(to: URL(fileURLWithPath: "\(out)/screen-\(i + 1).png"))
    print("\(out)/screen-\(i + 1).png")
}
