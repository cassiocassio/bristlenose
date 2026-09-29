import AppKit
import Testing
@testable import Bristlenose

/// The menu bar's fallback when the popout player is key: the report that
/// owns it. Without this every Video menu item dimmed with the player in
/// front (seen 29 Sep 2026).
@MainActor
struct PopoutOwnersTests {

    @Test func aPopoutAnswersWithItsOwner() {
        let owner = BridgeHandler()
        let popout = NSWindow()
        PopoutOwners.register(popout, owner: owner)
        #expect(PopoutOwners.owner(of: popout) === owner)
    }

    @Test func anyOtherWindowHasNoOwner() {
        #expect(PopoutOwners.owner(of: NSWindow()) == nil)
        #expect(PopoutOwners.owner(of: nil) == nil)
    }
}
