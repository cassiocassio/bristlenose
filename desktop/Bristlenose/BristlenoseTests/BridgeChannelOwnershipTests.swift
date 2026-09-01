import Foundation
import Testing
import WebKit
@testable import Bristlenose

/// Who owns `BridgeHandler.webView` — the outbound channel every native lens
/// affordance dispatches through.
///
/// The bug these pin (1 Sep 2026): `reset()` cleared the channel, so the field
/// had two writers with no defined order. When the incoming project's sidecar
/// was already warm, SwiftUI built the detail WebView in the same update pass
/// as the selection change — `makeNSView` registered, then `reset()` wiped it,
/// permanently, because nothing re-registers. Every sidebar lens row, the
/// rail, and ⌘1–⌘5 then dropped silently at the `guard let webView`, while
/// inbound messages kept arriving (they reach the Coordinator directly) — so
/// the lens capsule tracked the route and in-page links worked, and the app
/// looked entirely healthy while none of its own controls did anything.
///
/// The rule these tests hold: **the channel's lifetime follows the view**
/// (`makeNSView` registers, `dismantleNSView` deregisters if still current),
/// and nothing else writes it.
@MainActor
struct BridgeChannelOwnershipTests {

    /// The regression proper. Fails on the old `reset()`, which ended
    /// `webView = nil`.
    @Test func resetKeepsTheOutboundChannel() {
        let bridge = BridgeHandler()
        let webView = WKWebView()
        bridge.webView = webView

        bridge.reset()

        // If this fails: reset() is clearing the outbound channel again. A
        // warm-sidecar switch registers the new view BEFORE reset runs, so
        // that silently kills every native lens affordance for the document.
        #expect(bridge.webView === webView)
    }

    /// The ordering that actually shipped broken, replayed: register (as
    /// `makeNSView` does when the sidecar is already warm), then switch
    /// selection. The channel must survive, or the newly-mounted document is
    /// unreachable from native for its whole life.
    @Test func warmSwitchOrderingLeavesTheChannelUsable() {
        let bridge = BridgeHandler()
        let incoming = WKWebView()

        bridge.webView = incoming   // makeNSView, running first
        bridge.reset()              // applySelectionChange, running second
        bridge.handleMessage(["type": "ready"])

        #expect(bridge.webView === incoming)
        #expect(bridge.documentState == .spa)
    }

    /// `dismantleNSView` releases the channel when the registered view goes.
    @Test func dismantleClearsItsOwnRegistration() {
        let bridge = BridgeHandler()
        let coordinator = WebView.Coordinator(bridgeHandler: bridge, i18n: I18n())
        let webView = WKWebView()
        bridge.webView = webView

        WebView.dismantleNSView(webView, coordinator: coordinator)

        #expect(bridge.webView == nil)
    }

    /// …and never anyone else's. SwiftUI may build the replacement before
    /// tearing down its predecessor; an unguarded clear here would reproduce
    /// the same wipe from the other direction.
    @Test func dismantleOfASupersededViewLeavesTheCurrentOneAlone() {
        let bridge = BridgeHandler()
        let coordinator = WebView.Coordinator(bridgeHandler: bridge, i18n: I18n())
        let outgoing = WKWebView()
        let incoming = WKWebView()
        bridge.webView = incoming   // the replacement already registered

        WebView.dismantleNSView(outgoing, coordinator: coordinator)

        #expect(bridge.webView === incoming)
    }
}
