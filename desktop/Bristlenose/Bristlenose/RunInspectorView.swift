#if DEBUG
import SwiftUI
import WebKit

// MARK: - Run Inspector — DEBUG-only window
//
// Hosts the server's self-contained `/api/dev/run` infoviz page (the cost /
// timing / LLM-call story of the last pipeline run) in a WKWebView. Opened from
// the Debug menu; the whole file is `#if DEBUG`, like the TypeParity* set.
//
// Auth: `/api/dev/run` rides under `/api/`, so it's bearer-protected. The page
// is self-contained — it embeds its data and makes no further authenticated
// fetches — so a single authenticated top-level navigation suffices. We set the
// Authorization header on the initial `URLRequest` rather than relying on the
// SPA's auth cookie (this window never loads `/report/`, so no cookie is set).

struct RunInspectorView: View {
    @EnvironmentObject private var serveManager: ServeManager

    /// `/api/dev/run` on the running server, derived from the published serve URL
    /// (which points at `/report/`). Nil until the server is up.
    private var inspectorURL: URL? {
        guard let base = serveManager.serveURL,
              var comps = URLComponents(url: base, resolvingAgainstBaseURL: false)
        else { return nil }
        comps.path = "/api/dev/run"
        return comps.url
    }

    var body: some View {
        Group {
            if let url = inspectorURL, let token = serveManager.authToken {
                RunInspectorWebView(url: url, authToken: token)
            } else {
                ContentUnavailableView(
                    "Server not running",
                    systemImage: "bolt.horizontal.circle",
                    description: Text(
                        "Open a project so the analysis server starts, then reopen the Run Inspector."
                    )
                )
            }
        }
        .frame(minWidth: 720, minHeight: 480)
    }
}

private struct RunInspectorWebView: NSViewRepresentable {
    let url: URL
    let authToken: String

    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        // Ephemeral — no cross-window cookie/storage leakage.
        config.websiteDataStore = .nonPersistent()
        let webView = WKWebView(frame: .zero, configuration: config)
        // Web Inspector for free: right-click → Inspect Element on the in-app
        // window, instead of hunting the view in a detached Safari. Matches the
        // main report WebView (WebView.swift). DEBUG-only — the whole file is too.
        webView.isInspectable = true
        loadAuthed(into: webView)
        return webView
    }

    func updateNSView(_ webView: WKWebView, context: Context) {
        // Reload only when the target changes (the port shifts across serve
        // restarts), to avoid SwiftUI re-render reload loops.
        if webView.url?.absoluteString != url.absoluteString {
            loadAuthed(into: webView)
        }
    }

    /// `/api/dev/run` is bearer-protected. WKWebView does NOT reliably forward a
    /// custom `Authorization` header on a top-level document load, so we
    /// authenticate the navigation the way the server's middleware intends for
    /// plain browser navigations: the `bristlenose_auth` cookie (the same cookie
    /// the server sets when it serves `/report/`; this window never loads that,
    /// so we seed it ourselves). Cookie store writes are async — load only after
    /// it lands, or the first request races in uncredentialled. The Bearer header
    /// stays as belt-and-braces in case a future WebKit honours it.
    private func loadAuthed(into webView: WKWebView) {
        guard let cookie = authCookie else { webView.load(authedRequest); return }
        let store = webView.configuration.websiteDataStore.httpCookieStore
        store.setCookie(cookie) { webView.load(authedRequest) }
    }

    /// Matches `middleware.AUTH_COOKIE_NAME` / `app.py`'s `set_cookie`.
    private var authCookie: HTTPCookie? {
        guard let host = url.host else { return nil }
        return HTTPCookie(properties: [
            .name: "bristlenose_auth",
            .value: authToken,
            .domain: host,   // 127.0.0.1
            .path: "/",
        ])
    }

    private var authedRequest: URLRequest {
        var req = URLRequest(url: url)
        req.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")
        return req
    }
}
#endif
