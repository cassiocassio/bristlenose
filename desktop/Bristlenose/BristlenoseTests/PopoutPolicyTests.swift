import Foundation
import Testing
@testable import Bristlenose

/// Only the player page opens the popout window. Every other page on the serve
/// used to open there too, closing the player (docs/design-webview-context-menu.md
/// §3, the threshold-review timecode and Open Link in New Window).
@Suite("Popout policy")
struct PopoutPolicyTests {
    private func decide(_ s: String, port: Int? = 8150) -> PopoutPolicy.Decision {
        PopoutPolicy.decide(url: URL(string: s)!, allowedPort: port)
    }

    @Test func thePlayerPageOpensThePlayer() {
        #expect(decide("http://127.0.0.1:8150/report/assets/bristlenose-player.html#v=s1&t=12") == .player)
    }

    @Test func aReportPageIsRefused() {
        #expect(decide("http://127.0.0.1:8150/report/sessions/s1#t-754") == .refuse)
        #expect(decide("http://127.0.0.1:8150/report/quotes/") == .refuse)
        #expect(decide("http://127.0.0.1:8150/report/") == .refuse)
    }

    @Test func thePlayerPageOnAnotherPortIsNotOurs() {
        #expect(decide("http://127.0.0.1:9000/report/assets/bristlenose-player.html") == .external)
    }

    @Test func withNoLoadedPortNothingIsOurs() {
        #expect(decide("http://127.0.0.1:8150/report/assets/bristlenose-player.html", port: nil) == .external)
    }

    @Test func anImageOrAnOutsideLinkIsExternal() {
        #expect(decide("data:image/png;base64,AAAA") == .external)
        #expect(decide("https://bristlenose.app/docs/") == .external)
    }
}
