#if DEBUG
import AppKit
import OSLog
import SwiftUI
import WebKit

private let log = Logger(subsystem: "app.bristlenose", category: "typeparity")

// MARK: - Controller
//
// Owns the WKWebView for the parity tool, injects the live native metrics after
// load, and pulls the pixel-tuned spec back out for export. Mirrors the
// BridgeHandler ownership pattern (weak webView, callAsyncJavaScript with
// structured args). No localhost / auth — this view loads trusted local HTML.

@MainActor
final class TypeParityController: ObservableObject {
    weak var webView: WKWebView?

    /// Re-inject native metrics + sample + mode whenever they change. Called on
    /// load finish and on any control change in the SwiftUI top bar.
    func inject(rungs: [MacTypeRung], fingerprint: TypeParityFingerprint,
                sample: String, mode: String, smoothing: String) {
        guard let webView else { return }
        let payload = InjectPayload(
            native: Dictionary(uniqueKeysWithValues: rungs.map { ($0.id, $0) }),
            tokens: BNTokenLadder.rows,
            fingerprint: fingerprint,
            sample: sample,
            mode: mode,
            smoothing: smoothing
        )
        guard let data = try? JSONEncoder().encode(payload),
              let json = String(data: data, encoding: .utf8) else { return }
        // Structured argument (security rule 3) — no string interpolation into JS.
        Task { @MainActor in
            do {
                _ = try await webView.callAsyncJavaScript(
                    "window.__typeParityInit(JSON.parse(payload));",
                    arguments: ["payload": json],
                    in: nil, in: .page
                )
            } catch {
                log.error("inject failed: \(error.localizedDescription, privacy: .public)")
            }
        }
    }

    /// Pull the current (edited) spec out of the page, build CSS + JSON, and
    /// offer to save + copy to clipboard.
    func exportSpec() {
        guard let webView else { return }
        Task { @MainActor in
            do {
                let value = try await webView.callAsyncJavaScript(
                    "return window.__typeParityCollect();",
                    arguments: [:], in: nil, in: .page
                )
                guard let json = value as? String,
                      let data = json.data(using: .utf8),
                      let export = try? JSONDecoder().decode(TypeParityExport.self, from: data) else {
                    log.error("collect returned unexpected payload")
                    return
                }
                deliver(export: export)
            } catch {
                log.error("collect failed: \(error.localizedDescription, privacy: .public)")
            }
        }
    }

    private func deliver(export: TypeParityExport) {
        let css = TypeParitySpecBuilder.css(export)
        let json = TypeParitySpecBuilder.json(export)
        let combined = css + "\n\n/* --- JSON record --- */\n" + json

        // Clipboard always (cheapest path back into the editor / design doc).
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(combined, forType: .string)
        log.notice("type-parity spec copied to clipboard (\(export.rows.count) rows)")

        // Plus an explicit save panel for the two artefacts.
        let panel = NSSavePanel()
        panel.nameFieldStringValue = "tokens-desktop-tuned.css"
        panel.allowedContentTypes = [.plainText]
        panel.message = "CSS block + JSON record (also copied to clipboard)"
        if panel.runModal() == .OK, let url = panel.url {
            try? combined.write(to: url, atomically: true, encoding: .utf8)
        }
    }

    private struct InjectPayload: Codable {
        let native: [String: MacTypeRung]
        let tokens: [BNTokenRow]
        let fingerprint: TypeParityFingerprint
        let sample: String
        let mode: String
        let smoothing: String
    }
}

// MARK: - NSViewRepresentable

struct TypeParityWebView: NSViewRepresentable {
    @ObservedObject var controller: TypeParityController
    let rungs: [MacTypeRung]
    let fingerprint: TypeParityFingerprint
    let sample: String
    let mode: String
    let smoothing: String

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = context.coordinator
        webView.isInspectable = true   // DEBUG-only file; always inspectable here
        controller.webView = webView
        webView.loadHTMLString(TypeParityHTML.page, baseURL: nil)
        return webView
    }

    func updateNSView(_ webView: WKWebView, context: Context) {
        // Re-inject on any control change. The page is already loaded; init is
        // idempotent (it rebuilds rows from the payload each call).
        controller.inject(rungs: rungs, fingerprint: fingerprint,
                          sample: sample, mode: mode, smoothing: smoothing)
    }

    final class Coordinator: NSObject, WKNavigationDelegate {
        let parent: TypeParityWebView
        init(_ parent: TypeParityWebView) { self.parent = parent }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            // Capture only Sendable values + the @MainActor controller reference,
            // not the whole representable struct (which holds a property wrapper).
            let controller = parent.controller
            let rungs = parent.rungs
            let fingerprint = parent.fingerprint
            let sample = parent.sample
            let mode = parent.mode
            let smoothing = parent.smoothing
            Task { @MainActor in
                controller.inject(rungs: rungs, fingerprint: fingerprint,
                                  sample: sample, mode: mode, smoothing: smoothing)
            }
        }
    }
}
#endif
