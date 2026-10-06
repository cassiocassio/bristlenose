import Foundation
import Testing
@testable import Bristlenose

/// The report asks the Mac to re-analyse a session after a speaker recode
/// (design-people.md §J7 R3). The SPA has written the role pins through serve
/// first; this side only starts the ordinary resume run, so the request is a
/// counter the window observes, as the Discussion guide's is.
@MainActor
struct ReanalyseSessionBridgeTests {

    @Test func theRequestReachesTheWindow() {
        let bridge = BridgeHandler()
        #expect(bridge.reanalyseSessionRequests == 0)
        bridge.handleMessage(["type": "project-action", "action": "reanalyse-session",
                              "data": ["sessionId": "s3"]])
        #expect(bridge.reanalyseSessionRequests == 1)
    }

    @Test func anotherProjectActionDoesNotStartARun() {
        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "project-action", "action": "open-feedback"])
        #expect(bridge.reanalyseSessionRequests == 0)
    }
}
