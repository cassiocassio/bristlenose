// Throwaway control for "is divider-drag jank a fact of life?". NOT part of the repo.
//   lab <appkit|swiftui> <real|trivial> <out.json> [url]
// A bare WKWebView in a split view. Waits for the page, writes <out>.ready (divider position in
// CG screen coords), then measures between <out>.start and <out>.stop markers, writes <out>.
import AppKit
import SwiftUI
import WebKit

let args = CommandLine.arguments
guard args.count >= 4 else { print("usage: lab <appkit|swiftui> <real|trivial> <out.json> [url]"); exit(2) }
let mode = args[1], pageKind = args[2], outPath = args[3]
let realURL = args.count > 4 ? args[4] : "http://127.0.0.1:8499/report/quotes/"
let readyPath = outPath + ".ready", startPath = outPath + ".start", stopPath = outPath + ".stop"
for p in [outPath, readyPath, startPath, stopPath] { try? FileManager.default.removeItem(atPath: p) }

let labJS = """
(function(){
  const L={on:false,t:[],ro:0,long:[]};
  function tick(ts){ if(L.on) L.t.push(ts); requestAnimationFrame(tick); }
  requestAnimationFrame(tick);
  document.addEventListener('DOMContentLoaded',function(){
    try{ new ResizeObserver(function(){ if(L.on) L.ro++; }).observe(document.documentElement); }catch(e){}
  });
  try{ new PerformanceObserver(function(l){ if(L.on) for(const e of l.getEntries()) L.long.push(e.duration); }).observe({entryTypes:['longtask']}); }catch(e){}
  window.__lab={
    start:function(){L.t=[];L.ro=0;L.long=[];L.on=true;},
    stop:function(){
      L.on=false; const t=L.t; const g=[];
      for(let i=1;i<t.length;i++) g.push(t[i]-t[i-1]);
      const s=g.slice().sort(function(a,b){return a-b;});
      const q=function(p){return s.length?s[Math.min(s.length-1,Math.floor(p*s.length))]:0;};
      const dur=t.length>1?(t[t.length-1]-t[0])/1000:0;
      return {raf_frames:t.length,raf_seconds:dur,raf_fps:dur?t.length/dur:0,raf_gap_p50:q(.5),raf_gap_p95:q(.95),
        raf_gap_max:s.length?s[s.length-1]:0,raf_over33:g.filter(function(x){return x>33;}).length,
        raf_over50:g.filter(function(x){return x>50;}).length,
        dom_nodes:document.getElementsByTagName('*').length,text_len:(document.body?document.body.innerText.length:0),ro_callbacks:L.ro,longtasks:L.long.length,longtask_ms:L.long.reduce(function(a,b){return a+b;},0)};
    }
  };
})();
"""

var trivialHTML: String {
    var s = "<!doctype html><meta charset=utf-8><body style=\"font:15px -apple-system;margin:24px\"><h1>Control page</h1>"
    for i in 0..<120 { s += "<p>Paragraph \(i). The quick brown fox jumps over the lazy dog and keeps going so that the text must reflow whenever the width changes, which is the cheapest realistic layout work a page can ask for.</p>" }
    return s
}

let cfg = WKWebViewConfiguration()
let ucc = WKUserContentController()
ucc.addUserScript(WKUserScript(source: labJS, injectionTime: .atDocumentStart, forMainFrameOnly: true))
cfg.userContentController = ucc
let web = WKWebView(frame: .zero, configuration: cfg)
web.postsFrameChangedNotifications = true

var hostT: [Double] = []
var hostOn = false
var widthMin = Double.infinity, widthMax = 0.0
NotificationCenter.default.addObserver(forName: NSView.frameDidChangeNotification, object: web, queue: .main) { _ in
    guard hostOn else { return }
    hostT.append(CACurrentMediaTime())
    widthMin = min(widthMin, Double(web.frame.width)); widthMax = max(widthMax, Double(web.frame.width))
}

final class SideVC: NSViewController {
    override func loadView() { let v = NSVisualEffectView(); v.material = .sidebar; v.blendingMode = .behindWindow; view = v }
}
final class DetailVC: NSViewController { override func loadView() { view = web } }

struct WebRep: NSViewRepresentable {
    func makeNSView(context: Context) -> WKWebView { web }
    func updateNSView(_ v: WKWebView, context: Context) {}
}
struct Root: View {
    var body: some View {
        NavigationSplitView {
            List(0..<40, id: \.self) { Text("Item \($0)") }
                .navigationSplitViewColumnWidth(min: 200, ideal: 300, max: 400)
        } detail: { WebRep() }
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.regular)
let window = NSWindow(contentRect: NSRect(x: 100, y: 100, width: 1200, height: 800),
                      styleMask: [.titled, .closable, .resizable, .miniaturizable, .fullSizeContentView],
                      backing: .buffered, defer: false)
window.isReleasedWhenClosed = false
if mode == "appkit" {
    let split = NSSplitViewController()
    let s = NSSplitViewItem(sidebarWithViewController: SideVC())
    s.minimumThickness = 200; s.maximumThickness = 400
    split.addSplitViewItem(s)
    split.addSplitViewItem(NSSplitViewItem(viewController: DetailVC()))
    window.contentViewController = split
} else {
    window.contentViewController = NSHostingController(rootView: Root())
}
window.setFrame(NSRect(x: 100, y: 100, width: 1200, height: 800), display: true)
window.makeKeyAndOrderFront(nil)
app.activate(ignoringOtherApps: true)

func findSplit(_ v: NSView) -> NSSplitView? {
    if let s = v as? NSSplitView { return s }
    for c in v.subviews { if let s = findSplit(c) { return s } }
    return nil
}

func writeJSON(_ obj: [String: Any], to path: String) {
    if let d = try? JSONSerialization.data(withJSONObject: obj, options: [.prettyPrinted, .sortedKeys]) {
        try? d.write(to: URL(fileURLWithPath: path))
    }
}

func hostStats() -> [String: Any] {
    var gaps: [Double] = []
    if hostT.count > 1 { for i in 1..<hostT.count { gaps.append((hostT[i] - hostT[i - 1]) * 1000) } }
    let s = gaps.sorted()
    func q(_ p: Double) -> Double { s.isEmpty ? 0 : s[min(s.count - 1, Int(p * Double(s.count)))] }
    let dur = hostT.count > 1 ? hostT.last! - hostT.first! : 0
    return ["host_frame_changes": hostT.count, "host_seconds": dur, "host_fps": dur > 0 ? Double(hostT.count) / dur : 0,
            "host_gap_p50": q(0.5), "host_gap_p95": q(0.95), "host_gap_max": s.last ?? 0,
            "host_over33": gaps.filter { $0 > 33 }.count, "host_over50": gaps.filter { $0 > 50 }.count,
            "web_width_min": widthMin.isFinite ? widthMin : 0, "web_width_max": widthMax]
}

func becomeReady() {
    guard let sv = findSplit(window.contentView!) else { print("no split view found"); exit(3) }
    sv.setPosition(300, ofDividerAt: 0)
    sv.layoutSubtreeIfNeeded()
    DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
        let sidebar = sv.arrangedSubviews[0]
        let boundary = sidebar.frame.maxX
        let ptInSV = NSPoint(x: boundary + 0.5, y: sv.bounds.midY)
        let ptInWin = sv.convert(ptInSV, to: nil)
        let ptScreen = window.convertPoint(toScreen: ptInWin)
        let primaryH = NSScreen.screens[0].frame.height
        var hits: [String: String] = [:]
        for off in stride(from: -6.0, through: 6.0, by: 1.0) {
            let pw = sv.convert(NSPoint(x: boundary + off, y: sv.bounds.midY), to: nil)
            let hv = window.contentView!.superview!.hitTest(window.contentView!.superview!.convert(pw, from: nil))
            hits[String(format: "%+.0f", off)] = hv.map { String(describing: type(of: $0)) } ?? "nil"
        }
        writeJSON(["x": ptScreen.x, "y": primaryH - ptScreen.y, "sidebar_width": sidebar.frame.width,
                   "web_width": web.frame.width, "mode": mode, "page": pageKind, "hits": hits,
                   "divider_thickness": sv.dividerThickness, "divider_style": sv.dividerStyle.rawValue], to: readyPath)
        Timer.scheduledTimer(withTimeInterval: 0.05, repeats: true) { t in
            let fm = FileManager.default
            if fm.fileExists(atPath: startPath), !hostOn {
                hostT = []; widthMin = .infinity; widthMax = 0; hostOn = true
                web.evaluateJavaScript("window.__lab.start()", completionHandler: nil)
            }
            if fm.fileExists(atPath: stopPath), hostOn {
                hostOn = false; t.invalidate()
                web.evaluateJavaScript("JSON.stringify(window.__lab.stop())") { res, err in
                    var out = hostStats()
                    out["mode"] = mode; out["page"] = pageKind
                    if let str = res as? String, let d = str.data(using: .utf8),
                       let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any] { for (k, v) in j { out[k] = v } }
                    else { out["page_error"] = String(describing: err) }
                    writeJSON(out, to: outPath)
                    exit(0)
                }
            }
        }
    }
}

final class Nav: NSObject, WKNavigationDelegate {
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        DispatchQueue.main.asyncAfter(deadline: .now() + (pageKind == "real" ? 8.0 : 2.0)) { becomeReady() }
    }
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { print("nav fail: \(error)"); exit(4) }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { print("nav fail: \(error)"); exit(4) }
}
let nav = Nav()
web.navigationDelegate = nav
if pageKind == "real" { web.load(URLRequest(url: URL(string: realURL)!)) } else { web.loadHTMLString(trivialHTML, baseURL: nil) }
app.run()
