#if DEBUG
import SwiftUI
import WebKit

// MARK: - Run Inspector — DEBUG-only window
//
// Hosts the server's self-contained `/api/dev/run` infoviz page (the cost /
// timing / LLM-call story of the last pipeline run) in a WKWebView. Opened from
// the Debug menu; the whole file is `#if DEBUG`, like the TypeParity* set.
//
// Auth: `/api/dev/run` rides under `/api/`, so it's bearer-protected. WKWebView
// is unreliable here — it drops a custom `Authorization` header on a top-level
// navigation, and a cookie set via `httpCookieStore.setCookie` races the network
// process on the immediate next load (both observed as 401s in the window). So we
// take WKWebView out of the auth path entirely: fetch the page with `URLSession`
// (which honours the Bearer header), then render the returned self-contained HTML
// via `loadHTMLString`. The page embeds its own data and makes no further
// authenticated fetches, so a one-shot fetch is sufficient.

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
        context.coordinator.fetchAndRender(into: webView, url: url, token: authToken)
        return webView
    }

    func updateNSView(_ webView: WKWebView, context: Context) {
        // Re-fetch only when the target changes (the port shifts across serve
        // restarts), to avoid SwiftUI re-render loops.
        if context.coordinator.renderedURL?.absoluteString != url.absoluteString {
            context.coordinator.fetchAndRender(into: webView, url: url, token: authToken)
        }
    }

    func makeCoordinator() -> Coordinator { Coordinator() }

    @MainActor
    final class Coordinator {
        var renderedURL: URL?

        /// Fetch `/api/dev/run` with the Bearer header (URLSession honours it),
        /// then render the self-contained HTML string. `baseURL` is the request
        /// URL so the page's origin is the server (harmless — it makes no further
        /// requests). Non-200 / transport errors render a plain message instead.
        func fetchAndRender(into webView: WKWebView, url: URL, token: String) {
            renderedURL = url
            // Never blank: show what we're about to do, so even a hung fetch is
            // legible on screen.
            webView.loadHTMLString(
                Self.message("Loading…", "GET \(url.absoluteString)\ntoken present: \(!token.isEmpty)"),
                baseURL: nil
            )
            var req = URLRequest(url: url)
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
            Task { @MainActor in
                do {
                    let (data, response) = try await URLSession.shared.data(for: req)
                    let body = String(data: data, encoding: .utf8) ?? ""
                    let code = (response as? HTTPURLResponse)?.statusCode ?? 0
                    if code == 200 {
                        webView.loadHTMLString(body, baseURL: url)
                    } else {
                        // Surface status + body so a future failure is legible in
                        // the window itself (404 = sidecar missing the dev router,
                        // 401 = bad/empty token).
                        webView.loadHTMLString(Self.message("HTTP \(code)", body), baseURL: nil)
                    }
                } catch {
                    webView.loadHTMLString(
                        Self.message("Request failed", error.localizedDescription), baseURL: nil
                    )
                }
            }
        }

        private static func message(_ title: String, _ detail: String) -> String {
            let safe = detail
                .replacingOccurrences(of: "&", with: "&amp;")
                .replacingOccurrences(of: "<", with: "&lt;")
            return """
            <!doctype html><meta charset="utf-8">
            <body style="font:13px ui-monospace,monospace;background:#1a1a1c;color:#bbb;padding:24px">
            <b style="color:#eee">\(title)</b><pre style="white-space:pre-wrap">\(safe)</pre></body>
            """
        }
    }
}
#endif
