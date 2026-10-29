#if DEBUG
import SwiftUI
import WebKit

/// A contained WebKit rendering of the web application's *current* error
/// fallbacks. It belongs to Diagnostics ▸ Review Gallery, where it lets a
/// reviewer compare native and web behaviour without running a sidecar or
/// adding a fault-injection back door to the researcher-facing SPA.
///
/// The provenance label names the production component whose markup and rules
/// the specimen reflects. Keep this small: it is a review instrument, not a
/// second implementation of the report or a cross-surface contract.
struct ErrorPatternWebPreview: NSViewRepresentable {
    enum State: Equatable {
        case reportCrash
        case reportCrashAfterRetry
        case analysisFailed(String)
        case lens
        case part
        case notApplicable(String)

        var sourceLabel: String {
            switch self {
            case .reportCrash, .reportCrashAfterRetry: "RouteError.tsx · report scope"
            case .analysisFailed: "status_page.py · failed run"
            case .lens: "RouteError.tsx · lens scope"
            case .part: "PanelErrorBoundary.tsx · part fallback"
            case .notApplicable: "no web equivalent"
            }
        }
    }

    let state: State
    let onAction: (String) -> Void

    func makeCoordinator() -> Coordinator { Coordinator(onAction: onAction) }

    func makeNSView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        let content = WKUserContentController()
        content.add(context.coordinator, name: "review")
        configuration.userContentController = content
        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.setValue(false, forKey: "drawsBackground")
        webView.loadHTMLString(Self.html(for: state), baseURL: nil)
        return webView
    }

    func updateNSView(_ webView: WKWebView, context: Context) {
        context.coordinator.onAction = onAction
        webView.loadHTMLString(Self.html(for: state), baseURL: nil)
    }

    final class Coordinator: NSObject, WKScriptMessageHandler {
        var onAction: (String) -> Void

        init(onAction: @escaping (String) -> Void) { self.onAction = onAction }

        func userContentController(
            _ userContentController: WKUserContentController, didReceive message: WKScriptMessage
        ) {
            guard message.name == "review", let action = message.body as? String else { return }
            onAction("Web \(action) pressed (review specimen; no retry runs)")
        }
    }

    private static func html(for state: State) -> String {
        let body: String
        switch state {
        case .reportCrash:
            body = notice("This report couldn’t be shown.", button: "Retry")
        case .reportCrashAfterRetry:
            body = notice("This report couldn’t be shown.", button: "Give feedback", secondary: true)
        case .analysisFailed(let category):
            body = """
            <div class="report"><header>Checkout research</header><main>
              \(notice("The analysis didn’t finish.", button: category == "quota" ? "Retry" : "Show details"))
              <p class="context">Current category: \(escape(category))</p>
            </main></div>
            """
        case .lens:
            body = """
            <div class="report"><header>Checkout research</header><nav>Project &nbsp; Sessions &nbsp; Quotes</nav>
              <main>\(notice("This view couldn’t be shown.", button: "Retry"))</main></div>
            """
        case .part:
            body = """
            <div class="report"><header>Checkout research</header><nav>Project &nbsp; Sessions &nbsp; Quotes</nav>
              <main><section class="part" role="img" aria-label="This couldn’t be shown.">⌧</section><p class="context">The rest of the report is still available.</p></main></div>
            """
        case .notApplicable(let reason):
            body = "<div class=empty><p>\(escape(reason))</p></div>"
        }

        return """
        <!doctype html><html><head><meta charset="utf-8"><style>
        :root { color-scheme: light dark; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }
        * { box-sizing: border-box; } body { margin:0; min-height:100vh; color:light-dark(#1d1d1f,#f5f5f7); background:light-dark(#fff,#171717); }
        .report { min-height:100vh; } header { padding:16px 22px 10px; font-weight:600; border-bottom:1px solid light-dark(#e5e5ea,#38383a); }
        nav { padding:9px 22px; color:light-dark(#6e6e73,#a1a1a6); border-bottom:1px solid light-dark(#e5e5ea,#38383a); font-size:13px; }
        main { padding:22px; } .notice,.empty { min-height:210px; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; color:light-dark(#6e6e73,#a1a1a6); }
        p { margin:0 0 14px; } button { border:0; border-radius:6px; padding:7px 14px; font:inherit; background:#0a84ff; color:white; } button.secondary { background:light-dark(#f2f2f7,#363638); color:light-dark(#007aff,#0a84ff); }
        .part { width:42px; height:42px; display:grid; place-items:center; color:light-dark(#8e8e93,#98989d); font-size:28px; border:1px dashed light-dark(#c7c7cc,#48484a); border-radius:7px; } .context { font-size:12px; color:light-dark(#8e8e93,#98989d); margin-top:10px; }
        </style></head><body>\(body)</body></html>
        """
    }

    private static func notice(_ message: String, button: String, secondary: Bool = false) -> String {
        "<div class=notice role=alert><p>\(escape(message))</p><button class=\(secondary ? "secondary" : "") onclick=\"window.webkit.messageHandlers.review.postMessage('\\(escape(button))')\">\(escape(button))</button></div>"
    }

    private static func escape(_ text: String) -> String {
        text.replacingOccurrences(of: "&", with: "&amp;")
            .replacingOccurrences(of: "<", with: "&lt;")
            .replacingOccurrences(of: ">", with: "&gt;")
            .replacingOccurrences(of: "\"", with: "&quot;")
    }
}
#endif
