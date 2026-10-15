// Sandboxed WKWebView ink probe: the app's own WebKit, default WKWebViewConfiguration, under App Sandbox.
// A sandboxed binary must live in a bundle (exec'd bare it aborts with 133), and it cannot read the
// scratch dir, so the pages ship inside the bundle and the JSON goes to stdout.
//
//   P=<pages dir from gen-pages.mjs>; B=MonoProbe.app
//   mkdir -p $B/Contents/{MacOS,Resources} && cp $P/p-*.html $B/Contents/Resources/
//   /usr/libexec/PlistBuddy -c 'Add :CFBundleIdentifier string app.monoprobe-7c2e' \
//     -c 'Add :CFBundleExecutable string probe' -c 'Add :CFBundlePackageType string APPL' $B/Contents/Info.plist
//   swiftc -O -o $B/Contents/MacOS/probe probe-wkwebview.swift
//   codesign -s - -f --entitlements probe-wkwebview.entitlements $B
//   $B/Contents/MacOS/probe > $P/res-sb.json
//
// The probe asserts its own bundle id before reporting, so a clobbered bundle fails loudly.
import AppKit
import WebKit
import CryptoKit
let D = ""
var pages: [String: String] = [:]
guard Bundle.main.bundleIdentifier == "app.monoprobe-7c2e" else { FileHandle.standardError.write("wrong bundle\n".data(using:.utf8)!); exit(3) }
for sc in ["web","desktop","desktop_inter"] { pages[sc] = try! String(contentsOf: Bundle.main.url(forResource: "p-\(sc)", withExtension: "html")!, encoding: .utf8) }
let app = NSApplication.shared
app.setActivationPolicy(.accessory)
final class Runner: NSObject, WKNavigationDelegate {
    let wv: WKWebView; let win: NSWindow
    var scales = ["web","desktop","desktop_inter"]; var out: [[String: Any]] = []
    override init() {
        wv = WKWebView(frame: NSRect(x: 0, y: 0, width: 700, height: 900), configuration: WKWebViewConfiguration())
        win = NSWindow(contentRect: NSRect(x: -3000, y: 0, width: 700, height: 900), styleMask: [.borderless], backing: .buffered, defer: false)
        super.init(); win.contentView = wv; win.orderFrontRegardless(); wv.navigationDelegate = self; next()
    }
    func next() {
        guard let s = scales.first else {
            let data = try! JSONSerialization.data(withJSONObject: out)
            FileHandle.standardOutput.write(data); exit(0)
        }
        wv.loadHTMLString(pages[s]!, baseURL: nil)
    }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        let js = "document.fonts.ready.then(()=>JSON.stringify({h:document.documentElement.scrollHeight,b:[...document.querySelectorAll('span[data-k]')].map(e=>{const r=e.getBoundingClientRect();return [e.dataset.k,r.y,r.width,getComputedStyle(e).fontSize]})}))"
        wv.callAsyncJavaScript("return await " + js, arguments: [:], in: nil, in: .page) { res in
            let obj = try! JSONSerialization.jsonObject(with: (try! res.get() as! String).data(using: .utf8)!) as! [String: Any]
            let H = (obj["h"] as! NSNumber).doubleValue
            self.wv.setFrameSize(NSSize(width: 700, height: H)); self.win.setContentSize(NSSize(width: 700, height: H))
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) { self.shoot(obj["b"] as! [[Any]]) }
        }
    }
    func shoot(_ boxes: [[Any]]) {
        let cfg = WKSnapshotConfiguration(); cfg.rect = wv.bounds; cfg.afterScreenUpdates = true
        wv.takeSnapshot(with: cfg) { img, err in
            let cg = img!.cgImage(forProposedRect: nil, context: nil, hints: nil)!
            let W = cg.width, Hh = cg.height; let k = Double(W) / 700.0
            var buf = [UInt8](repeating: 0, count: W * Hh * 4)
            let ctx = CGContext(data: &buf, width: W, height: Hh, bitsPerComponent: 8, bytesPerRow: W * 4, space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
            ctx.draw(cg, in: CGRect(x: 0, y: 0, width: W, height: Hh))
            let s = self.scales.removeFirst()
            for b in boxes {
                let key = b[0] as! String; let y = (b[1] as! NSNumber).doubleValue; let w = (b[2] as! NSNumber).doubleValue
                let top = floor(y / 40) * 40; let y0 = Int(top * k), y1 = Int((top + 40) * k)
                var ink = 0.0; var md = Insecure.MD5()
                for yy in y0..<min(y1, Hh) { let off = yy * W * 4
                    md.update(data: Data(buf[off..<off + W * 4]))
                    for x in 0..<W { let i = off + x * 4; ink += 255 - (Double(buf[i]) * 0.299 + Double(buf[i+1]) * 0.587 + Double(buf[i+2]) * 0.114) } }
                let parts = key.split(separator: "|").map(String.init)
                let hash = md.finalize().map { String(format: "%02x", $0) }.joined().prefix(10)
                self.out.append(["engine": "sandboxed-webkit", "scale": s, "stack": parts[0], "size": parts[1], "px": b[3], "weight": Int(parts[2])!, "width": w, "ink": Int(ink / 255), "hash": String(hash), "scaleFactor": k])
            }
            self.next()
        }
    }
}
let r = Runner()
app.run()
