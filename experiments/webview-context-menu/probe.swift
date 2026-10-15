import AppKit
import WebKit

// Standalone probe: what WebKit puts in a WKWebView's context menu for a link,
// an image (http and data:), text and background; where each item routes; and
// whether a bridge post from the page's `contextmenu` event lands before
// `willOpenMenu`. Not Bristlenose code.

func now() -> Double { ProcessInfo.processInfo.systemUptime * 1000 }
var log: [String] = []
func L(_ s: String) { let line = String(format: "%10.2f ", now()) + s; log.append(line); print(line); fflush(stdout) }

final class ProbeWebView: WKWebView {
    var onMenu: ((NSMenu) -> Void)?
    override func willOpenMenu(_ menu: NSMenu, with event: NSEvent) {
        L("willOpenMenu items=\(menu.items.count)")
        for (i, it) in menu.items.enumerated() {
            L("  [\(i)] id=\(it.identifier?.rawValue ?? "-") title=\(it.isSeparatorItem ? "----" : it.title) action=\(it.action.map(NSStringFromSelector) ?? "-") sub=\(it.submenu?.items.count ?? 0)")
        }
        super.willOpenMenu(menu, with: event)
        onMenu?(menu)
    }
}

final class Probe: NSObject, WKScriptMessageHandler, WKUIDelegate, WKNavigationDelegate, WKDownloadDelegate {
    var webView: ProbeWebView!
    var window: NSWindow!
    var server: HTTPServer!
    var steps: [() -> Void] = []
    var lastMenu: NSMenu?

    func userContentController(_ u: WKUserContentController, didReceive m: WKScriptMessage) {
        L("bridge message: \(m.body)")
    }
    func webView(_ w: WKWebView, createWebViewWith c: WKWebViewConfiguration, for a: WKNavigationAction, windowFeatures f: WKWindowFeatures) -> WKWebView? {
        L("createWebViewWith url=\(a.request.url?.absoluteString.prefix(60) ?? "nil") navType=\(a.navigationType.rawValue) targetFrame=\(a.targetFrame == nil ? "nil" : "set")")
        return nil
    }
    func webView(_ w: WKWebView, decidePolicyFor a: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        L("decidePolicyFor url=\(a.request.url?.absoluteString.prefix(60) ?? "nil") navType=\(a.navigationType.rawValue) shouldDownload=\(a.shouldPerformDownload) main=\(a.targetFrame?.isMainFrame ?? false)")
        if a.shouldPerformDownload { decisionHandler(.download); return }
        decisionHandler(.allow)
    }
    func webView(_ w: WKWebView, navigationAction: WKNavigationAction, didBecome d: WKDownload) { L("download(navAction) url=\(navigationAction.request.url?.absoluteString.prefix(60) ?? "nil")"); d.delegate = self }
    func webView(_ w: WKWebView, navigationResponse: WKNavigationResponse, didBecome d: WKDownload) { L("download(navResponse)"); d.delegate = self }
    func download(_ d: WKDownload, decideDestinationUsing r: URLResponse, suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) {
        L("download decideDestination suggested=\(suggestedFilename) mime=\(r.mimeType ?? "-") url=\(r.url?.absoluteString.prefix(60) ?? "nil")")
        completionHandler(nil)
    }
}

final class HTTPServer {
    // Tiny loopback server: page with a link, an http image, a data: image, text.
    let fd: Int32; let port: UInt16
    init() {
        let fd = socket(AF_INET, SOCK_STREAM, 0)
        self.fd = fd
        var yes: Int32 = 1; setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &yes, 4)
        var addr = sockaddr_in(); addr.sin_family = sa_family_t(AF_INET); addr.sin_port = 0; addr.sin_addr.s_addr = inet_addr("127.0.0.1")
        _ = withUnsafePointer(to: &addr) { $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { bind(fd, $0, socklen_t(MemoryLayout<sockaddr_in>.size)) } }
        listen(fd, 16)
        var len = socklen_t(MemoryLayout<sockaddr_in>.size)
        _ = withUnsafeMutablePointer(to: &addr) { $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { getsockname(fd, $0, &len) } }
        self.port = UInt16(bigEndian: addr.sin_port)
        Thread.detachNewThread { [fd] in
            while true {
                let c = accept(fd, nil, nil); if c < 0 { continue }
                var buf = [UInt8](repeating: 0, count: 4096); let n = read(c, &buf, 4096)
                let req = String(decoding: buf.prefix(max(n, 0)), as: UTF8.self)
                let path = req.split(separator: " ").dropFirst().first.map(String.init) ?? "/"
                var body: Data; var type = "text/html"
                if path.hasPrefix("/img.png") {
                    body = Data(base64Encoded: "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")!; type = "image/png"
                } else {
                    body = Data(PAGE.utf8)
                }
                let head = "HTTP/1.1 200 OK\r\nContent-Type: \(type)\r\nContent-Length: \(body.count)\r\nConnection: close\r\n\r\n"
                _ = head.withCString { write(c, $0, strlen($0)) }
                _ = body.withUnsafeBytes { write(c, $0.baseAddress, body.count) }
                close(c)
            }
        }
    }
}

let PNG_DATA = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
let PAGE = """
<!doctype html><html><body style="margin:0;font:16px sans-serif">
<a id=link href="/report/sessions/s1#t-120" style="position:absolute;left:10px;top:10px;width:200px;height:30px;display:block;background:#eef">internal link</a>
<img id=img src="/img.png" style="position:absolute;left:10px;top:60px;width:100px;height:60px">
<img id=dimg src="\(PNG_DATA)" style="position:absolute;left:150px;top:60px;width:100px;height:60px">
<p id=txt style="position:absolute;left:10px;top:140px">Plain text paragraph here</p>
<a id=ext href="https://example.com/" style="position:absolute;left:10px;top:180px;width:200px;height:30px;display:block">external link</a>
<button id=btn style="position:absolute;left:10px;top:230px;width:120px;height:30px">button</button>
<script>
document.addEventListener("contextmenu", (e) => {
  const a = e.target.closest("a"); const img = e.target.closest("img");
  window.webkit.messageHandlers.probe.postMessage({ev:"contextmenu", target:e.target.id, href:a?a.getAttribute("href"):null, img:img?img.src.slice(0,30):null, t:performance.now()});
});
</script></body></html>
"""

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let probe = Probe()
let srv = HTTPServer(); probe.server = srv
let cfg = WKWebViewConfiguration()
cfg.userContentController.add(probe, name: "probe")
let wv = ProbeWebView(frame: NSRect(x: 0, y: 0, width: 400, height: 300), configuration: cfg)
wv.uiDelegate = probe; wv.navigationDelegate = probe
probe.webView = wv
let win = NSWindow(contentRect: NSRect(x: 200, y: 200, width: 400, height: 300), styleMask: [.titled], backing: .buffered, defer: false)
win.contentView = wv; win.makeKeyAndOrderFront(nil); probe.window = win
app.activate(ignoringOtherApps: true)
wv.load(URLRequest(url: URL(string: "http://127.0.0.1:\(srv.port)/report/")!))

// CSS (top-left origin) → window coords (bottom-left)
func rightClick(_ x: CGFloat, _ yTop: CGFloat) {
    let p = NSPoint(x: x, y: 300 - yTop)
    let e = NSEvent.mouseEvent(with: .rightMouseDown, location: p, modifierFlags: [], timestamp: ProcessInfo.processInfo.systemUptime, windowNumber: win.windowNumber, context: nil, eventNumber: 0, clickCount: 1, pressure: 1)!
    L("-> rightMouseDown at css(\(x),\(yTop))")
    win.sendEvent(e)
}

// Which menu item to fire after the menu for each target closes.
let plan: [(String, CGFloat, CGFloat, String?)] = [
    ("link", 50, 25, "WKMenuItemIdentifierOpenLinkInNewWindow"),
    ("link", 50, 25, "WKMenuItemIdentifierOpenLink"),
    ("link", 50, 25, "WKMenuItemIdentifierDownloadLinkedFile"),
    ("img-http", 40, 80, "WKMenuItemIdentifierOpenImageInNewWindow"),
    ("img-http", 40, 80, "WKMenuItemIdentifierDownloadImage"),
    ("img-data", 180, 80, "WKMenuItemIdentifierOpenImageInNewWindow"),
    ("img-data", 180, 80, "WKMenuItemIdentifierDownloadImage"),
    ("text", 40, 150, nil),
    ("background", 350, 280, nil),
    ("external", 50, 195, "WKMenuItemIdentifierOpenLinkInNewWindow"),
    ("button", 40, 245, nil),
]
var idx = 0
var pendingFire: String?
wv.onMenu = { menu in
    probe.lastMenu = menu
    // Close the menu shortly; fire the chosen item after it has closed.
    let t = Timer(timeInterval: 0.4, repeats: false) { _ in menu.cancelTracking() }
    RunLoop.current.add(t, forMode: .eventTracking)
    RunLoop.current.add(t, forMode: .common)
}
func runNext() {
    if let id = pendingFire, let menu = probe.lastMenu,
       let item = menu.items.first(where: { $0.identifier?.rawValue == id }) {
        L("firing \(id) target=\(String(describing: item.target)) action=\(item.action.map(NSStringFromSelector) ?? "-")")
        if let i = menu.items.firstIndex(of: item) { menu.performActionForItem(at: i) }
    } else if let id = pendingFire { L("NOT FOUND in menu: \(id)") }
    pendingFire = nil; probe.lastMenu = nil
    guard idx < plan.count else {
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
            exit(0)
        }
        return
    }
    let (name, x, y, fire) = plan[idx]; idx += 1
    L("=== target \(name) (fire: \(fire ?? "none"))")
    pendingFire = fire
    rightClick(x, y)
    DispatchQueue.main.asyncAfter(deadline: .now() + 1.6) { runNext() }
}
DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) { runNext() }
DispatchQueue.main.asyncAfter(deadline: .now() + 60) { L("TIMEOUT"); exit(2) }
app.run()
