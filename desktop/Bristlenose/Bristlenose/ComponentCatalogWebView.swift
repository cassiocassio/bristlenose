#if DEBUG
import SwiftUI
import WebKit

// MARK: - Web column for the Component Catalogue
//
// Renders the SAME components as the native column, but via the web design
// system (real bn token values), inside a WKWebView. Self-contained HTML — no
// serve, no auth, no localhost (mirrors the TypeParityWebView pattern). Ephemeral
// store because the sandboxed persistent store wedges the WebContent renderer.

struct ComponentCatalogWebView: NSViewRepresentable {
    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .nonPersistent()
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.isInspectable = true   // DEBUG-only harness; always inspectable
        webView.loadHTMLString(ComponentCatalogHTML.page, baseURL: nil)
        return webView
    }

    func updateNSView(_ nsView: WKWebView, context: Context) {}
}
#endif
