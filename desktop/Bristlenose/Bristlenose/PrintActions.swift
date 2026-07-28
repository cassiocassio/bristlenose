import AppKit
import WebKit

/// File ▸ Page Setup… and File ▸ Print… for the report web view.
///
/// Both items previously dispatched over the web bridge as
/// `menuAction("pageSetup")` / `menuAction("print")`, which **no SPA handler
/// ever consumed** — so both were silent no-ops despite looking fully enabled.
///
/// Printing a WKWebView is a native concern, not something the page can do for
/// us: `window.print()` inside a WKWebView does not raise the macOS print
/// panel, so routing these through the bridge was the wrong target from the
/// start. `NSPrintOperation` is the right one.
///
/// **Per-lens printing is free.** The operation renders the web view's *current*
/// document, so whichever lens is on screen — Sessions, Quotes, Codebook,
/// Analysis — prints itself with no per-lens work. Print fidelity is then a CSS
/// concern (`@media print` in the theme), not a Swift one.
@MainActor
enum PrintActions {

    /// Standard macOS Page Setup panel.
    ///
    /// Edits the shared `NSPrintInfo`, which `print(webView:window:)` reads —
    /// so paper size, orientation and margins chosen here carry into the next
    /// print. That shared-state coupling is the AppKit convention, not an
    /// accident: it's why Page Setup is a sibling menu item rather than a
    /// section of the print panel.
    static func pageSetup() {
        NSApp.runPageLayout(nil)
    }

    /// Print the report web view's current contents.
    ///
    /// Two details are load-bearing:
    /// - **`operation.view?.frame` must be set explicitly.** A WKWebView print
    ///   operation whose view carries a zero or stale frame prints blank or
    ///   clipped pages — that frame is what the pagination machinery measures.
    /// - **Sheet, not free-floating panel.** `runModal(for:)` attaches the print
    ///   panel to the window. The window-less `run()` fallback exists only so a
    ///   print can never silently do nothing (cf. the drop-initiated-NSSavePanel
    ///   gotcha in `desktop/CLAUDE.md`, where a nil key window produced a
    ///   detached, wrongly-themed panel).
    ///
    /// Takes the web view as a parameter rather than reaching for
    /// `BridgeHandler.webView` itself so the call site owns the "which window?"
    /// question — today there is one shared web view reference, so this inherits
    /// the same front-window caveat as every other menu action (see
    /// `docs/design-workspace.md` §Window-scoping, Stage 2).
    static func print(webView: WKWebView?, window: NSWindow?) {
        guard let webView else { return }

        let operation = webView.printOperation(with: NSPrintInfo.shared)
        operation.showsPrintPanel = true
        operation.showsProgressPanel = true
        operation.view?.frame = webView.bounds

        if let window {
            operation.runModal(for: window, delegate: nil, didRun: nil, contextInfo: nil)
        } else {
            operation.run()
        }
    }
}
