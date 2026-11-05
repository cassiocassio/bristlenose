import Cocoa
import WebKit
// usage: wk <url> [runs] — a new non-persistent WKWebView per run (earlier views are kept alive, so only the first
// run pays WebKit's content-process launch: read the "all ready" list, not only the median). The window is
// transparent and may be throttled as occluded, unlike the app's visible one.
final class H: NSObject, WKScriptMessageHandler {
    var readyAt: Double?
    func userContentController(_ c: WKUserContentController, didReceive m: WKScriptMessage) {
        if let d = m.body as? [String: Any], d["type"] as? String == "ready", readyAt == nil { readyAt = Date().timeIntervalSince1970 * 1000 }
    }
}
let args = CommandLine.arguments
guard args.count >= 2, let url = URL(string: args[1]) else { print("usage: wk <report-url> [runs]"); exit(2) }
let runs = args.count > 2 ? (Int(args[2]) ?? 5) : 5
let app = NSApplication.shared; app.setActivationPolicy(.accessory)
var results: [[String: Double]] = []
var keep: [AnyObject] = []
func runOnce(_ done: @escaping () -> Void) {
    let h = H()
    let cfg = WKWebViewConfiguration()
    cfg.websiteDataStore = .nonPersistent()
    cfg.userContentController.add(h, name: "navigation")
    cfg.userContentController.addUserScript(WKUserScript(source: "window.__BRISTLENOSE_EMBEDDED__ = true;", injectionTime: .atDocumentStart, forMainFrameOnly: true))
    let web = WKWebView(frame: NSRect(x: 0, y: 0, width: 1200, height: 800), configuration: cfg)
    let win = NSWindow(contentRect: web.frame, styleMask: [.titled], backing: .buffered, defer: false)
    win.contentView = web; win.alphaValue = 0; win.orderFrontRegardless()
    let nav = Nav(); web.navigationDelegate = nav; keep.append(nav); keep.append(web); keep.append(win); keep.append(h)
    let t0 = Date().timeIntervalSince1970 * 1000
    web.load(URLRequest(url: url))
    var tick = 0
    Timer.scheduledTimer(withTimeInterval: 0.02, repeats: true) { t in
        tick += 1
        if h.readyAt != nil || tick > 600 {
            t.invalidate()
            let js = "JSON.stringify((()=>{const r=performance.getEntriesByType('resource');const js=r.filter(x=>x.name.endsWith('.js'));return {nRes:r.length,nJs:js.length,lastJsEnd:Math.max(...js.map(x=>x.responseEnd)),dcl:performance.getEntriesByType('navigation')[0].domContentLoadedEventEnd}})())"
            web.evaluateJavaScript(js) { v, _ in
                var row: [String: Double] = ["ready": (h.readyAt ?? 0) - t0, "didStart": (nav.started ?? 0) - t0, "didFinish": (nav.finished ?? 0) - t0]
                if let s = v as? String, let d = try? JSONSerialization.jsonObject(with: Data(s.utf8)) as? [String: Double] { row.merge(d) { $1 } }
                if h.readyAt != nil { results.append(row) } else { print("run timed out (no ready after 12 s): not counted") }
                done()
            }
        }
    }
}
final class Nav: NSObject, WKNavigationDelegate {
    var started: Double?; var finished: Double?
    func webView(_ w: WKWebView, didStartProvisionalNavigation n: WKNavigation!) { started = Date().timeIntervalSince1970 * 1000 }
    func webView(_ w: WKWebView, didFinish n: WKNavigation!) { finished = Date().timeIntervalSince1970 * 1000 }
}
var i = 0
func next() {
    if i >= runs {
        func med(_ k: String) -> Int { let v = results.compactMap { $0[k] }.sorted(); return v.isEmpty ? -1 : Int(v[v.count / 2]) }
        print(["ready", "didStart", "didFinish", "dcl", "lastJsEnd", "nRes", "nJs"].map { "\($0)=\(med($0))" }.joined(separator: " "))
        print("all ready:", results.map { Int($0["ready"] ?? -1) })
        exit(0)
    }
    i += 1; runOnce { DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) { next() } }
}
DispatchQueue.main.async { next() }
app.run()
